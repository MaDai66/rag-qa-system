from concurrent.futures import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import JobLookupError
from datetime import datetime, timedelta
from src.utils.logger import get_logger
logger = get_logger(__name__)

class TaskSchedulerManager:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.current_job = None
        # self.executor = ThreadPoolExecutor(max_workers=2)

    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("⏰ 调度器已启动")

    def shutdown(self, wait=True):
        """关闭调度器"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=wait)
                logger.info("🛑 调度器已关闭")
        except JobLookupError:
            logger.warning("⚠️ 关闭调度器时未找到相关任务")
        finally:
            # self.executor.shutdown(wait=wait)  # 关闭线程池
            logger.info("🧵 线程池已关闭")

    def schedule_task_after_completion(self, func, delay_seconds=5):
        """
        在指定函数执行完毕后，延迟一段时间再次执行该函数
        """
        def wrapped():
            try:
                logger.info(f"🛫 开始执行任务: {func.__name__}")
                # future = self.executor.submit(func)  # 提交任务到线程池
                # future.result()  # 等待执行完成
                func()
                logger.info(f"✅ 任务 {func.__name__} 执行完成")
            except Exception as e:
                logger.error(f"❌ 任务 {func.__name__} 执行出错: {e}", exc_info=True)
            finally:
                # 任务完成后，安排下一次执行
                self.scheduler.add_job(
                    wrapped,
                    'date',
                    run_date=datetime.now() + timedelta(seconds=delay_seconds),
                    misfire_grace_time=None
                )

        # 首次触发任务
        self.current_job = self.scheduler.add_job(
            wrapped,
            'date',
            run_date=datetime.now() + timedelta(seconds=0),
            misfire_grace_time=None
        )
        logger.info(f"🕒 已安排首次任务: {func.__name__}")