@echo off
cd /d "C:\Users\Vladimir Vasilev\projects\bg-realestate-scraper"
call .venv\Scripts\activate.bat
bgscraper run-once
bgscraper send-daily
bgscraper generate-site
