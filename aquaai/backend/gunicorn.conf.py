import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
threads = 8
timeout = 60
worker_tmp_dir = "/dev/shm"
accesslog = "-"
errorlog = "-"
