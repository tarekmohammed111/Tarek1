import os
import asyncio
import logging
import tempfile
import secrets
import string
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List

from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class AdvancedBotHosting:
    def __init__(self, token: str):
        self.token = token
        self.user_bots: Dict[int, Dict] = {}
        self.bot_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.user_sessions: Dict[int, Dict] = {}
        
        # إعداد المجلدات
        self.bots_dir = "hosted_bots"
        self.logs_dir = "bots_logs"
        os.makedirs(self.bots_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
    
    def generate_bot_token(self) -> str:
        """إنشاء توكن عشوائي للبوتات"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(35))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """بدء النظام"""
        user = update.effective_user
        welcome_text = f"""
🤖 **مرحباً {user.first_name} في نظام استضافة البوتات المتقدم!**

🎯 **الإمكانيات المتاحة:**
• رفع بوتات بايثون كاملة
• إدارة متعددة للبوتات
• نظام logs متقدم
• تشغيل 24/7
• إدارة كاملة عبر الأوامر

📋 **الأوامر المتاحة:**
/start - بدء النظام
/deploy - رفع بوت جديد  
/mybots - قائمة بوتاتك
/stop [id] - إيقاف بوت
/restart [id] - إعادة تشغيل بوت
/logs [id] - مشاهدة logs
/status - حالة النظام

⚡ **أرسل ملف البوت أو استخدم /deploy**
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    async def deploy_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """بدء عملية رفع بوت جديد"""
        user_id = update.effective_user.id
        
        self.user_sessions[user_id] = {
            'waiting_for_file': True,
            'step': 'awaiting_file'
        }
        
        await update.message.reply_text(
            "📤 **مرحلة رفع البوت**\n\n"
            "1. أرسل ملف البوت (.py)\n"
            "2. تأكد من وجود المتطلبات في الملف\n"
            "3. البوت سيشغل تلقائياً\n\n"
            "⚡ أرسل الملف الآن..."
        )
    
    async def handle_python_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة ملفات البايثون"""
        user_id = update.effective_user.id
        
        # التحقق من وجود جلسة نشطة
        if user_id not in self.user_sessions or not self.user_sessions[user_id].get('waiting_for_file'):
            await update.message.reply_text("❌ استخدم /deploy أولاً لبدء رفع بوت")
            return
        
        try:
            await update.message.reply_text("🔄 جاري معالجة البوت...")
            
            # تحميل الملف
            file = await update.message.document.get_file()
            file_name = update.message.document.file_name
            
            if not file_name.endswith('.py'):
                await update.message.reply_text("❌ يرجى إرسال ملف بايثون فقط (.py)")
                return
            
            # إنشاء معرف فريد للبوت
            bot_id = f"bot_{user_id}_{int(datetime.now().timestamp())}"
            bot_dir = os.path.join(self.bots_dir, bot_id)
            os.makedirs(bot_dir, exist_ok=True)
            
            # حفظ الملف
            file_path = os.path.join(bot_dir, "main.py")
            await file.download_to_drive(file_path)
            
            # قراءة وتحليل الكود
            with open(file_path, 'r', encoding='utf-8') as f:
                code_content = f.read()
            
            # فحص الأمان
            security_check = await self.security_scan(code_content)
            if not security_check['safe']:
                await update.message.reply_text(f"❌ **مشكلة أمان:** {security_check['reason']}")
                return
            
            # إنشاء ملف متطلبات
            await self.create_requirements(bot_dir, code_content)
            
            # تثبيت المتطلبات
            install_success = await self.install_requirements(bot_dir)
            if not install_success:
                await update.message.reply_text("⚠️ فشل تثبيت بعض المتطلبات، جاري التشغيل بأدنى إعدادات...")
            
            # تشغيل البوت
            bot_process = await self.start_user_bot(bot_dir, bot_id)
            
            if bot_process:
                # حفظ معلومات البوت
                self.user_bots[user_id] = self.user_bots.get(user_id, {})
                self.user_bots[user_id][bot_id] = {
                    'process': bot_process,
                    'dir': bot_dir,
                    'start_time': datetime.now(),
                    'status': 'running',
                    'log_file': os.path.join(self.logs_dir, f"{bot_id}.log")
                }
                
                # إنشاء ملف log
                with open(self.user_bots[user_id][bot_id]['log_file'], 'w') as f:
                    f.write(f"Bot {bot_id} started at {datetime.now()}\n")
                
                # تنظيف الجلسة
                self.user_sessions[user_id]['waiting_for_file'] = False
                
                await update.message.reply_text(
                    f"✅ **تم نشر البوت بنجاح!**\n\n"
                    f"🆔 **معرف البوت:** `{bot_id}`\n"
                    f"⏰ **وقت البدء:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"📊 **الحالة:** 🟢 شغال\n\n"
                    f"استخدم:\n"
                    f"/mybots - لعرض بوتاتك\n"
                    f"/stop {bot_id} - لإيقاف البوت\n"
                    f"/logs {bot_id} - لمشاهدة السجلات"
                )
            else:
                await update.message.reply_text("❌ فشل تشغيل البوت، تأكد من صحة الكود")
            
        except Exception as e:
            logger.error(f"Error handling file: {e}")
            await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
    
    async def security_scan(self, code: str) -> Dict:
        """فحص أمان الكود"""
        dangerous_patterns = [
            'os.system', 'subprocess.call', 'subprocess.Popen',
            'eval(', 'exec(', 'compile(',
            '__import__', 'importlib',
            'open(', 'write(', 'shutil.',
            'rmdir', 'remove', 'unlink',
            'requests.post', 'urllib.request',
            'socket.socket'
        ]
        
        for pattern in dangerous_patterns:
            if pattern in code:
                return {'safe': False, 'reason': f'الكود يحتوي على {pattern}'}
        
        return {'safe': True, 'reason': 'الكود آمن'}
    
    async def create_requirements(self, bot_dir: str, code: str):
        """إنشاء ملف المتطلبات تلقائياً"""
        common_libs = {
            'python-telegram-bot': 'python-telegram-bot',
            'requests': 'requests',
            'aiohttp': 'aiohttp',
            'pymongo': 'pymongo',
            'sqlalchemy': 'sqlalchemy',
            'psycopg2': 'psycopg2-binary',
            'mysql': 'mysql-connector-python',
        }
        
        requirements = []
        for lib, package in common_libs.items():
            if f'import {lib}' in code or f'from {lib}' in code:
                requirements.append(package)
        
        # إضافة المتطلبات الأساسية
        if not requirements:
            requirements = ['python-telegram-bot>=20.0']
        
        req_path = os.path.join(bot_dir, "requirements.txt")
        with open(req_path, 'w') as f:
            for req in requirements:
                f.write(f"{req}\n")
    
    async def install_requirements(self, bot_dir: str) -> bool:
        """تثبيت متطلبات البوت"""
        try:
            req_file = os.path.join(bot_dir, "requirements.txt")
            if os.path.exists(req_file):
                process = await asyncio.create_subprocess_exec(
                    'pip', 'install', '-r', req_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.wait()
                return process.returncode == 0
            return True
        except Exception as e:
            logger.error(f"Requirements install failed: {e}")
            return False
    
    async def start_user_bot(self, bot_dir: str, bot_id: str) -> asyncio.subprocess.Process:
        """تشغيل بوت المستخدم"""
        try:
            main_file = os.path.join(bot_dir, "main.py")
            
            # إنشاء عملية منفصلة للبوت
            process = await asyncio.create_subprocess_exec(
                'python', main_file,
                cwd=bot_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            self.bot_processes[bot_id] = process
            
            # مراقبة العملية
            asyncio.create_task(self.monitor_bot_process(bot_id, process))
            
            return process
            
        except Exception as e:
            logger.error(f"Failed to start bot {bot_id}: {e}")
            return None
    
    async def monitor_bot_process(self, bot_id: str, process: asyncio.subprocess.Process):
        """مراقبة عملية البوت"""
        try:
            # انتظار انتهاء العملية
            return_code = await process.wait()
            
            # تحديث الحالة
            for user_id, bots in self.user_bots.items():
                if bot_id in bots:
                    self.user_bots[user_id][bot_id]['status'] = 'stopped'
                    self.user_bots[user_id][bot_id]['end_time'] = datetime.now()
                    
                    # تسجيل في الlog
                    log_file = self.user_bots[user_id][bot_id]['log_file']
                    with open(log_file, 'a') as f:
                        f.write(f"Bot stopped with return code: {return_code}\n")
                    
                    break
                    
        except Exception as e:
            logger.error(f"Error monitoring bot {bot_id}: {e}")
    
    async def list_user_bots(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض بوتات المستخدم"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_bots or not self.user_bots[user_id]:
            await update.message.reply_text("📭 لا توجد بوتات نشطة لديك")
            return
        
        bots_list = "🤖 **بوتاتك النشطة:**\n\n"
        for bot_id, bot_info in self.user_bots[user_id].items():
            status_icon = "🟢" if bot_info['status'] == 'running' else "🔴"
            bots_list += f"{status_icon} `{bot_id}` - {bot_info['status']}\n"
        
        bots_list += "\nاستخدم /stop [id] أو /logs [id] للإدارة"
        await update.message.reply_text(bots_list, parse_mode='Markdown')
    
    async def stop_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إيقاف بوت محدد"""
        user_id = update.effective_user.id
        
        if not context.args:
            await update.message.reply_text("❌ يرجى تحديد معرف البوت: /stop [bot_id]")
            return
        
        bot_id = context.args[0]
        
        if user_id not in self.user_bots or bot_id not in self.user_bots[user_id]:
            await update.message.reply_text("❌ البوت غير موجود أو لا ينتمي لك")
            return
        
        bot_info = self.user_bots[user_id][bot_id]
        
        if bot_info['status'] == 'running':
            process = bot_info['process']
            if process and process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
            
            bot_info['status'] = 'stopped'
            bot_info['end_time'] = datetime.now()
            
            await update.message.reply_text(f"🛑 تم إيقاف البوت `{bot_id}`", parse_mode='Markdown')
        else:
            await update.message.reply_text("⏹️ البوت متوقف بالفعل")
    
    async def show_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض سجلات البوت"""
        user_id = update.effective_user.id
        
        if not context.args:
            await update.message.reply_text("❌ يرجى تحديد معرف البوت: /logs [bot_id]")
            return
        
        bot_id = context.args[0]
        
        if user_id not in self.user_bots or bot_id not in self.user_bots[user_id]:
            await update.message.reply_text("❌ البوت غير موجود أو لا ينتمي لك")
            return
        
        log_file = self.user_bots[user_id][bot_id]['log_file']
        
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                logs = f.read()
            
            if len(logs) > 4000:
                logs = logs[-4000:]  # آخر 4000 حرف فقط
            
            await update.message.reply_text(f"📋 **سجلات البوت {bot_id}:**\n```\n{logs}\n```", parse_mode='Markdown')
        else:
            await update.message.reply_text("📭 لا توجد سجلات للبوت")
    
    async def system_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """حالة النظام"""
        total_bots = sum(len(bots) for bots in self.user_bots.values())
        running_bots = sum(
            1 for user_bots in self.user_bots.values() 
            for bot in user_bots.values() 
            if bot['status'] == 'running'
        )
        
        status_text = f"""
📊 **حالة نظام الاستضافة:**

• 🤖 إجمالي البوتات: {total_bots}
• 🟢 البوتات النشطة: {running_bots}
• 🔴 البوتات المتوقفة: {total_bots - running_bots}
• 👥 المستخدمين: {len(self.user_bots)}

💾 **المساحة:** {self.get_disk_usage()}
        """
        await update.message.reply_text(status_text, parse_mode='Markdown')
    
    def get_disk_usage(self) -> str:
        """الحصول على استخدام المساحة"""
        try:
            total, used, free = shutil.disk_usage("/")
            return f"{used // (2**30)}GB / {total // (2**30)}GB"
        except:
            return "غير متاح"

# التنفيذ الرئيسي
def main():
    # استبدل TOKEN_HERE بتوكن البوت الخاص بك
    TOKEN = "7800490136:AAEyTmajl8_c20YGxUaaJF1mDnGQGBq9oUk"
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إنشاء نظام الاستضافة
    hosting_system = AdvancedBotHosting(TOKEN)
    
    # إضافة الhandlers
    application.add_handler(CommandHandler("start", hosting_system.start))
    application.add_handler(CommandHandler("deploy", hosting_system.deploy_bot))
    application.add_handler(CommandHandler("mybots", hosting_system.list_user_bots))
    application.add_handler(CommandHandler("stop", hosting_system.stop_bot))
    application.add_handler(CommandHandler("logs", hosting_system.show_logs))
    application.add_handler(CommandHandler("status", hosting_system.system_status))
    application.add_handler(MessageHandler(filters.Document.ALL, hosting_system.handle_python_file))
    
    # بدء البوت
    logger.info("🚀 نظام استضافة البوتات يعمل الآن!")
    application.run_polling()

if __name__ == '__main__':
    import shutil
    main()