"""
搜索任务管理服务（V2.0 新增）
管理客户发现任务的整个生命周期：
关键词扩展 -> 缓存检查 -> Google搜索 -> 过滤 -> 标准化 -> 去重 -> 自动分析 -> 保存
支持断点续跑、失败重试
"""
import json
import datetime
import asyncio
import logging
from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from app.database import SessionLocal, Customer, SearchTask
from app.services.url_normalizer import normalize_url
from app.services.company_filter import filter_search_results, is_blacklisted
from app.services.cache_manager import (
    get_search_cache,
    save_search_cache,
    get_website_cache,
    save_website_cache,
    get_analysis_cache,
    save_analysis_cache,
)
from app.services.retry_manager import retry_async
from app.services.keyword_expander import expand_keywords
from app.services.google_discovery import search_google
from app.services.website_scraper import scrape_website
from app.services.email_extractor import extract_emails_from_text
from app.services.keyword_analyzer import analyze_keywords
from app.services.glm_analyzer import analyze_company, generate_summary
from app.services.scoring_engine import calculate_scores
from app.services.deduplication import find_existing_customer, normalize_company_name

logger = logging.getLogger("search_task")
# ── 任务停止控制 ──
# _task_stop_flags: 按 search_task.id 独立控制每个搜索任务的停止
# _batch_stop_flag: 控制客户列表页的「停止分析」（批量 AI 分析）
_task_stop_flags: Dict[int, bool] = {}
_batch_stop_flag: bool = False


def request_stop():
    """请求停止批量客户分析（stop_analysis端点）"""
    global _batch_stop_flag
    _batch_stop_flag = True


def request_task_stop(task_id: int):
    """请求停止指定搜索任务"""
    _task_stop_flags[task_id] = True


def reset_stop_flag():
    """重置所有停止标记（兼容旧接口，新代码请直接调用具体函数）"""
    global _batch_stop_flag
    _batch_stop_flag = False
    _task_stop_flags.clear()


def should_stop(task_id: Optional[int] = None) -> bool:
    """检查是否应该停止

    Args:
        task_id: 搜索任务ID。传入则检查该任务是否被单独停止；
                 不传入则检查全局批量停止标记。
    """
    if task_id is not None and _task_stop_flags.get(task_id):
        return True
    return _batch_stop_flag


async def run_search_task(task_id: int):
    """
    执行搜索任务（包含完整的发现+分析流程，支持断点续跑）

    完整流程：
    1. 更新任务状态为Running
    2. AI扩展关键词（如果还没扩展）
    3. 遍历扩展关键词：
       a. 检查搜索缓存（30天内有效）
       b. Google搜索
       c. 过滤非企业官网
       d. 网址标准化
       e. 去重（检查是否已存在）
       f. 自动进入V1分析流程（官网抓取 -> 邮箱提取 -> 关键词分析 -> AI分析 -> 规则评分）
       g. 保存到数据库
    4. 更新任务状态为Completed
    """
    # 初始化本任务的停止标记（清理旧标记）
    _task_stop_flags.pop(task_id, None)

    db = SessionLocal()
    try:
        task = db.query(SearchTask).filter(SearchTask.id == task_id).first()
        if not task:
            logger.error(f"任务 {task_id} 不存在")
            return

        # 更新状态为Running
        task.status = "Running"
        db.commit()

        logger.info(f"开始执行搜索任务 {task_id}: {task.country} / {task.keyword}")
        _append_task_log(task, "info", f"搜索任务开始: {task.country} / {task.keyword}")
        db.commit()

        # 步骤1：AI扩展关键词（如果还未扩展）
        expanded_keywords = []
        if task.expanded_keywords:
            try:
                expanded_keywords = json.loads(task.expanded_keywords)
                if not isinstance(expanded_keywords, list):
                    expanded_keywords = []
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"任务 {task_id} 的 expanded_keywords 数据损坏，重新扩展")
                task.expanded_keywords = None
        if not expanded_keywords:
            logger.info(f"正在扩展关键词: {task.keyword}")
            expanded = await expand_keywords(task.keyword, country=task.country)
            if expanded and len(expanded) > 0:
                expanded_keywords = expanded
            else:
                expanded_keywords = [task.keyword]

            task.expanded_keywords = json.dumps(expanded_keywords, ensure_ascii=False)
            _append_task_log(task, "success", f"AI扩展关键词完成，共 {len(expanded_keywords)} 个")
            db.commit()
            logger.info(f"关键词扩展完成，共 {len(expanded_keywords)} 个")

        # 步骤2：从断点处继续
        start_index = task.current_keyword_index

        for idx in range(start_index, len(expanded_keywords)):
            # 检查停止标记
            if should_stop(task_id):
                logger.info(f"任务 {task_id} 被用户停止")
                _append_task_log(task, "warning", f"用户停止任务（已处理 {idx}/{len(expanded_keywords)} 个关键词）")
                task.status = "Paused"
                task.current_keyword_index = idx
                db.commit()
                return

            # 每次处理新关键词前重置状态（如果之前被暂停过）
            if task.status != "Running":
                task.status = "Running"
                db.commit()

            keyword = expanded_keywords[idx]
            logger.info(f"[{idx+1}/{len(expanded_keywords)}] 搜索关键词: {keyword}")
            _append_task_log(task, "info", f"[{idx+1}/{len(expanded_keywords)}] 搜索: {keyword}")
            db.commit()

            # 更新当前进度
            task.current_keyword_index = idx
            task.status = "Running"
            db.commit()

            # 步骤3：检查搜索缓存
            cached_results = get_search_cache(db, keyword, task.country)
            if cached_results:
                logger.info(f"使用搜索缓存: {keyword} ({len(cached_results)}条)")
                search_results = cached_results
                _append_task_log(task, "info", f"缓存命中: 「{keyword}」({len(cached_results)}条)")
                db.commit()
            else:
                # 步骤4：Google搜索
                search_results = await retry_async(
                    search_google,
                    keyword=keyword,
                    country=task.country,
                    max_results=task.search_depth or 50,
                    max_retries=2,
                    retry_delay=3.0,
                    task_name=f"Google搜索[{keyword}]",
                )
                if not search_results:
                    search_results = []

                # 保存到搜索缓存
                save_search_cache(db, keyword, task.country, search_results)
                _append_task_log(task, "success", f"搜索完成: 「{keyword}」({len(search_results)}条)")
                db.commit()
                logger.info(f"Google搜索完成: {keyword} ({len(search_results)}条)")

            # 步骤5：过滤非企业官网
            filtered_results = filter_search_results(search_results)
            remaining = len(filtered_results)
            total = len(search_results)
            if remaining < total:
                _append_task_log(task, "info", f"过滤非企业官网: {total} → {remaining}条有效")
            else:
                _append_task_log(task, "info", f"搜索结果: {remaining}条有效")
            db.commit()
            logger.info(f"过滤后剩余: {remaining}/{total}条")

            task.found_websites = (task.found_websites or 0) + len(filtered_results)

            # 步骤6：遍历每个搜索结果
            for result in filtered_results:
                # 检查停止标记
                if should_stop(task_id):
                    _append_task_log(task, "warning", f"用户停止，当前处理到第 {idx+1}/{len(expanded_keywords)} 个关键词")
                    task.status = "Paused"
                    task.current_keyword_index = idx
                    db.commit()
                    return

                raw_url = result.get("website", "")
                if not raw_url:
                    continue

                # 网址标准化
                domain = normalize_url(raw_url)

                # 二次检查黑名单
                if is_blacklisted(domain):
                    continue

                # 检查数据库是否已存在相同客户（域名 + 公司名双重去重）
                company_title = result.get("title", "") or result.get("name", "")
                existing = find_existing_customer(db, domain, company_title)

                if existing:
                    # 合并发现关键词
                    old_kw = existing.discovery_keyword or ""
                    if keyword and keyword not in old_kw:
                        existing.discovery_keyword = f"{old_kw}, {keyword}" if old_kw else keyword
                    now = datetime.datetime.utcnow()
                    if existing.first_found_at is None or now < existing.first_found_at:
                        existing.first_found_at = now
                    db.commit()
                    logger.info(f"跳过已存在的公司（合并关键词）: {domain}")
                    _append_task_log(task, "info", f"跳过重复: {domain}（合并关键词）")
                    db.commit()
                    task.analyzed_companies = (task.analyzed_companies or 0) + 1
                    continue

                # 自动进入V1分析流程
                try:
                    await _auto_analyze_and_save(
                        db=db,
                        domain=domain,
                        country=task.country,
                        discovery_keyword=keyword,
                        title=result.get("title", ""),
                        task_id=task_id,
                    )
                    task.new_companies = (task.new_companies or 0) + 1
                    task.analyzed_companies = (task.analyzed_companies or 0) + 1
                except Exception as e:
                    logger.error(f"分析失败 {domain}: {str(e)[:100]}")
                    _append_task_log(task, "error", f"分析失败: {domain} — {str(e)[:80]}")
                    db.commit()
                    continue

        # 任务完成
        task.status = "Completed"
        task.finished_at = datetime.datetime.utcnow()
        _append_task_log(task, "success",
            f"搜索任务完成！共处理 {len(expanded_keywords)} 个关键词，"
            f"发现 {task.found_websites} 个网站，新增 {task.new_companies} 个公司")
        db.commit()
        logger.info(f"搜索任务 {task_id} 完成，新增 {task.new_companies} 个公司")

    except Exception as e:
        logger.error(f"搜索任务 {task_id} 异常: {str(e)[:200]}")
        db.rollback()
        task = db.query(SearchTask).filter(SearchTask.id == task_id).first()
        if task:
            task.status = "Failed"
            task.error_message = str(e)[:500]
            _append_task_log(task, "error", f"任务异常终止: {str(e)[:200]}")
            db.commit()
    finally:
        db.close()


async def _auto_analyze_and_save(
    db: Session,
    domain: str,
    country: str,
    discovery_keyword: str,
    title: str,
    task_id: Optional[int] = None,
):
    """
    自动执行完整的V1分析流程：
    官网抓取(缓存) -> 邮箱提取 -> 关键词分析 -> AI分析(缓存) -> 规则评分 -> 保存
    自动去重：按域名和公司名检查，已存在则跳过分析
    """
    website = f"https://{domain}"
    now = datetime.datetime.utcnow()

    # ── 去重检查：已存在的客户不重复创建 ──
    from app.services.deduplication import find_existing_customer

    existing = find_existing_customer(db, domain, title)
    if existing:
        # 更新发现关键词（合并新的关键词）
        old_kw = existing.discovery_keyword or ""
        discovery_kw = discovery_keyword or ""
        if old_kw and discovery_kw and discovery_kw not in old_kw:
            existing.discovery_keyword = f"{old_kw}, {discovery_kw}"
        elif not old_kw:
            existing.discovery_keyword = discovery_kw
        # 更新首次发现时间（取最早的）
        if existing.first_found_at is None or now < existing.first_found_at:
            existing.first_found_at = now
        db.commit()
        logger.info(f"跳过重复客户（已存在）: {domain} / {title[:40]}")
        return

    # 创建新客户记录
    customer = Customer(
        company_name=title[:255] if title else domain,
        website=domain,
        country=country,
        city="",  # Google 搜索结果暂无城市信息，后续可通过 AI 分析补充
        discovery_source="Google",
        discovery_keyword=discovery_keyword,
        first_found_at=now,
        created_at=now,
    )
    db.add(customer)
    db.flush()  # 获取id

    # 步骤1：官网抓取（检查缓存）
    cached_website = get_website_cache(db, domain)
    if cached_website:
        website_text = cached_website["content"]
        customer.scrape_status = "success"
        logger.info(f"使用官网缓存: {domain}")
    else:
        website_text = await retry_async(
            scrape_website,
            website,
            max_retries=2,
            task_name=f"官网抓取[{domain}]",
        )
        if website_text:
            customer.scrape_status = "success"
            save_website_cache(db, domain, website_text)
        else:
            customer.scrape_status = "failed"
            customer.fail_reason = "官网抓取失败（网站可能无法访问或反爬）"
            db.commit()
            logger.warning(f"官网抓取失败: {domain}")
            # 没有官网内容就不继续了
            customer.analyzed_at = datetime.datetime.utcnow()
            db.commit()
            return

    if website_text:
        customer.website_text = website_text

        # 检查停止标记 — 爬取完成后，AI分析前
        if should_stop(task_id):
            logger.info(f"停止信号已触发，跳过 {domain} 的AI分析")
            customer.analyzed_at = datetime.datetime.utcnow()
            db.commit()
            return

        # 步骤2：邮箱提取
        emails = extract_emails_from_text(website_text)
        email_list = list(set(emails))
        customer.emails = json.dumps(email_list, ensure_ascii=False)

        # 步骤3：关键词分析
        pos_hits, neg_hits = analyze_keywords(website_text)
        customer.positive_keywords = json.dumps(pos_hits, ensure_ascii=False)
        customer.negative_keywords = json.dumps(neg_hits, ensure_ascii=False)

        # 步骤4：DeepSeek AI分析（检查缓存）
        cached_analysis = get_analysis_cache(db, domain, website_text)
        if cached_analysis:
            ai_result = cached_analysis
            logger.info(f"使用AI分析缓存: {domain}")
        else:
            # 检查停止标记 — AI分析前（AI分析是最耗时步骤）
            if should_stop(task_id):
                logger.info(f"停止信号已触发，跳过 {domain} 的AI分析")
                customer.analyzed_at = datetime.datetime.utcnow()
                db.commit()
                return

            ai_result = await retry_async(
                analyze_company,
                website_text,
                max_retries=2,
                task_name=f"AI分析[{domain}]",
            )
            if ai_result:
                customer.ai_status = "success"
                save_analysis_cache(db, domain, website_text, ai_result)
            else:
                customer.ai_status = "failed"
                customer.fail_reason = "AI分析失败（API可能超时）"

        if ai_result:
            customer.ai_raw_json = json.dumps(ai_result, ensure_ascii=False)
            customer.company_type = ai_result.get("company_type", "")
            customer.sales_hook = ai_result.get("sales_hook", "")
            customer.target_position = ai_result.get("target_position", "")
            customer.identified_projects = ai_result.get("identified_projects", "")
            # AI 提取城市（如果有且客户尚无 city）
            ai_city = ai_result.get("address_city", "")
            if ai_city and not customer.city:
                customer.city = ai_city.strip()
            customer_info = {"country": country, "company_name": title}
            customer.ai_summary = generate_summary(ai_result, customer_info)

        # 步骤5：规则评分
        scores = calculate_scores(
            website_text=website_text,
            positive_keywords=pos_hits,
            company_type=customer.company_type,
            country=country,
            emails=email_list,
        )

        customer.industry_score = scores["industry_score"]
        customer.project_score = scores["project_score"]
        customer.company_type_score = scores["company_type_score"]
        customer.country_score = scores["country_score"]
        customer.contact_score = scores["contact_score"]
        customer.total_score = scores["total_score"]
        customer.priority = scores["priority"]

    customer.analyzed_at = datetime.datetime.utcnow()
    db.commit()
    logger.info(f"新公司自动分析完成: {domain} (评分: {customer.total_score})")


def get_paused_tasks(db: Session) -> List[SearchTask]:
    """获取所有已暂停的任务（用于断点续跑）"""
    return db.query(SearchTask).filter(
        SearchTask.status == "Paused"
    ).all()


def resume_paused_task(task_id: int):
    """标记暂停任务为Pending，以便重新调度"""
    db = SessionLocal()
    try:
        task = db.query(SearchTask).filter(SearchTask.id == task_id).first()
        if task and task.status == "Paused":
            task.status = "Pending"
            db.commit()
            return True
        return False
    finally:
        db.close()


def _append_task_log(task, type_: str, msg: str):
    """
    向任务的 task_log 字段追加一条结构化日志

    Args:
        task: SearchTask 实例
        type_: 日志类型 — "info" / "success" / "warning" / "error"
        msg: 日志消息内容
    """
    logs = []
    if task.task_log:
        try:
            logs = json.loads(task.task_log)
        except (json.JSONDecodeError, TypeError):
            pass
    now = datetime.datetime.utcnow().strftime("%H:%M:%S")
    logs.append({"time": now, "type": type_, "msg": str(msg)[:200]})
    task.task_log = json.dumps(logs, ensure_ascii=False)
