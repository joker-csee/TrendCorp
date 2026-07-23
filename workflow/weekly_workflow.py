# workflow/weekly_workflow.py — 周度主线扫描 + 中军筛选
from datetime import date

from workflow.base import BaseWorkflow
from data.providers.market_provider import MarketProvider
from engine.scanner.scanner import MarketScanner
from engine.theme_selector import ThemeSelector
from engine.screener.screener import CoreScreener
from repositories.sector_repository import SectorRepository
from repositories.stock_repository import StockRepository
from repositories.core_score_repository import CoreScoreRepository


class WeeklyWorkflow(BaseWorkflow):
    """周日执行：更新板块 → 扫描 → 确认主线 → 筛选中军 → 持久化。"""

    def __init__(self, market: MarketProvider,
                 scanner: MarketScanner,
                 theme_selector: ThemeSelector,
                 screener: CoreScreener,
                 sector_repo: SectorRepository,
                 stock_repo: StockRepository,
                 core_score_repo: CoreScoreRepository):
        super().__init__()
        self.market = market
        self.scanner = scanner
        self.selector = theme_selector
        self.screener = screener
        self.sector_repo = sector_repo
        self.stock_repo = stock_repo
        self.core_score_repo = core_score_repo

    def execute(self):
        today = date.today()
        snap = today.isoformat()

        # Step 1: 更新板块列表
        self.logger.info("Step 1/5: 更新全市场板块列表")
        df = self.market.fetch_all_sectors()
        sector_count = 0
        for _, row in df.iterrows():
            try:
                sid = self.sector_repo.upsert_sector(
                    code=str(row["code"]),
                    name=str(row["name"]),
                    sec_type=str(row["type"]),
                )
                sector_count += 1
            except Exception as e:
                self.logger.warning("板块入库失败 %s: %s", row.get("code"), e)
        self.logger.info("板块更新完成，共 %d 个", sector_count)

        # Step 2: 扫描板块
        self.logger.info("Step 2/5: 扫描板块（B-1 四维评分）")
        scan_results = self.scanner.scan_all(today)
        self.logger.info("候选板块: %d 个", len(scan_results))

        # Step 3: 确认主线
        self.logger.info("Step 3/5: 确认主线（B-2 持续性验证）")
        classified = self.selector.confirm(scan_results)
        confirmed = classified["confirmed"]
        self.logger.info(
            "主线确认: %d 确认 + %d 观察 + %d 排除",
            len(confirmed),
            len(classified.get("watch", [])),
            len(classified.get("excluded", [])),
        )

        # Step 4: 筛选中军
        self.logger.info("Step 4/5: 筛选中军（C-1 五维评分）")
        total_cores = 0
        for theme in confirmed:
            sec_code = theme.get("sector_code", "")
            sec_name = theme.get("sector_name", "")
            sec_type = theme.get("sec_type", "concept")
            try:
                cores = self.screener.screen(sec_code, sec_name, sec_type, today)
                total_cores += len(cores)
                # 中军标的入库
                for core in cores:
                    try:
                        sector_id = (
                            self.sector_repo.get_by_code(sec_code) or {}
                        ).get("id")
                        stock_id = self.stock_repo.upsert_stock(
                            code=core.stock_code,
                            name=core.stock_name,
                            sector_id=sector_id,
                        )
                        self.core_score_repo.save_snapshot(
                            stock_id=stock_id,
                            snap_date=snap,
                            market_cap_score=core.market_cap_score,
                            liquidity_score=core.liquidity_score,
                            ma_structure_score=core.ma_structure_score,
                            vol_health_score=core.vol_health_score,
                            fundamental_score=core.fundamental_score,
                            total_score=core.total_score,
                            price=core.price, ma5=core.ma5,
                            ma10=core.ma10, ma21=core.ma21, ma55=core.ma55,
                            ma_deviation=core.ma_deviation,
                            vol_ratio_20=core.vol_ratio_20,
                            signal=core.signal,
                        )
                    except Exception as e:
                        self.logger.warning(
                            "中军入库失败 %s: %s", core.stock_code, e
                        )
            except Exception as e:
                self.logger.warning("板块 %s 中军筛选失败: %s", sec_code, e)

        # Step 5: 保存板块快照
        self.logger.info("Step 5/5: 保存板块扫描快照")
        for r in scan_results:
            try:
                sec = self.sector_repo.get_by_code(r.sector_code)
                if sec:
                    self.sector_repo.save_snapshot(
                        sector_id=sec["id"],
                        snap_date=snap,
                        trend_score=r.trend_score,
                        rel_strength=r.rel_strength,
                        fund_score=r.fund_score,
                        echelon_score=r.echelon_score,
                        total_score=r.total_score,
                        ma5=r.ma5, ma10=r.ma10, ma21=r.ma21, ma55=r.ma55,
                        ret_20d=r.ret_20d, hs300_ret_20d=r.hs300_ret_20d,
                        fund_flow_5d=r.fund_flow_5d,
                        limit_up_cnt=r.limit_up_cnt,
                        volume_ratio=r.volume_ratio,
                    )
            except Exception as e:
                self.logger.warning(
                    "快照保存失败 %s: %s", r.sector_code, e
                )

        self.logger.info(
            "完成: %d 确认主线, %d 只中军, %d 个板块快照",
            len(confirmed), total_cores, len(scan_results),
        )
