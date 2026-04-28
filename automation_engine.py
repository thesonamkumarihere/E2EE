import random
import os
import json
import time
import platform
import threading
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains

# File paths
COOKIES_PATH = Path(__file__).parent / 'cookies.json'
TIME_PATH = Path(__file__).parent / 'time.txt'
HATERS_NAME_PATH = Path(__file__).parent / 'hatersname.txt'
CONVO_PATH = Path(__file__).parent / 'convo.txt'
MESSAGES_PATH = Path(__file__).parent / 'NP.txt'

# Global variable for message rotation
message_rotation_index = 0

def read_config_from_files():
    """Read configuration from text files"""
    try:
        # Read cookies from cookies.json
        cookies = ''
        if COOKIES_PATH.exists():
            with open(COOKIES_PATH, 'r', encoding='utf-8') as f:
                cookies_data = json.load(f)
                cookies = cookies_data.get('facebook_cookies', '')

        # Read delay time from time.txt
        delay = '30'
        if TIME_PATH.exists():
            delay = TIME_PATH.read_text(encoding='utf-8').strip() or '30'

        # Read target name from hatersname.txt
        haters_name = ''
        if HATERS_NAME_PATH.exists():
            haters_name = HATERS_NAME_PATH.read_text(encoding='utf-8').strip()

        # Read chat_id from convo.txt
        chat_id = ''
        if CONVO_PATH.exists():
            chat_id = CONVO_PATH.read_text(encoding='utf-8').strip()

        # Read messages from NP.txt
        messages = ['Hello! Default message from deployment']
        if MESSAGES_PATH.exists():
            messages_content = MESSAGES_PATH.read_text(encoding='utf-8')
            messages = [line.strip() for line in messages_content.split('\n') if line.strip()]

        return {
            'cookies': cookies,
            'delay': delay,
            'haters_name': haters_name,
            'chat_id': chat_id,
            'messages': messages
        }
    except Exception as error:
        print(f'Error reading config files: {error}')
        return {
            'cookies': '',
            'delay': '30',
            'haters_name': '',
            'chat_id': '',
            'messages': ['Hello! Default message from deployment']
        }

def get_next_message(messages):
    """Get next message in rotation"""
    global message_rotation_index
    if not messages or len(messages) == 0:
        return 'Hello! Default message from deployment'
    
    message = messages[message_rotation_index % len(messages)]
    message_rotation_index += 1
    return message

def find_message_input(driver, log_callback=None):
    """Find message input field on Facebook"""
    if log_callback:
        log_callback('Finding message input...')
    
    time.sleep(5)
    
    message_input_selectors = [
        'div[contenteditable="true"][role="textbox"]',
        'div[contenteditable="true"][data-lexical-editor="true"]',
        'div[aria-label*="message" i][contenteditable="true"]',
        'div[aria-label*="Message" i][contenteditable="true"]',
        'div[aria-label*="Type" i][contenteditable="true"]',
        'div[aria-label*="Write" i][contenteditable="true"]',
        'div[aria-label*="Send" i][contenteditable="true"]',
        'div[contenteditable="true"][spellcheck="true"]',
        '[role="textbox"][contenteditable="true"]',
        '[aria-label="Message"][contenteditable="true"]',
        '[aria-label="Type a message"][contenteditable="true"]',
        'textarea[placeholder*="message" i]',
        'textarea[placeholder*="Message" i]',
        '[contenteditable="true"]'
    ]
    
    for selector in message_input_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            
            for element in elements:
                try:
                    if element.is_displayed() and element.size['width'] > 0 and element.size['height'] > 0:
                        element.click()
                        time.sleep(1)
                        
                        is_editable = driver.execute_script("""
                            return arguments[0].contentEditable === 'true' || 
                                   arguments[0].tagName === 'TEXTAREA' || 
                                   arguments[0].tagName === 'INPUT';
                        """, element)
                        
                        if is_editable:
                            element_text = driver.execute_script("return arguments[0].placeholder || arguments[0].getAttribute('aria-label') || '';", element).lower()
                            
                            if any(keyword in element_text for keyword in ['message', 'write', 'type', 'send', 'chat']):
                                if log_callback:
                                    log_callback(f'Found message input with: {selector}')
                                return element
                except Exception:
                    continue
        except Exception:
            continue
    
    return None

def setup_browser(log_callback=None):
    """Setup Chrome browser for headless deployment"""
    if log_callback:
        log_callback('Setting up Chrome browser...')
    
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-setuid-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--ignore-certificate-errors')
    
    # Try to find Chrome/Chromium paths
    chromium_paths = [
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/usr/bin/google-chrome',
        '/usr/bin/chrome'
    ]
    
    for chromium_path in chromium_paths:
        if Path(chromium_path).exists():
            chrome_options.binary_location = chromium_path
            if log_callback:
                log_callback(f'Found Chrome at: {chromium_path}')
            break
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_window_size(1920, 1080)
        if log_callback:
            log_callback('Browser setup completed!')
        return driver
    except Exception as error:
        if log_callback:
            log_callback(f'Browser setup failed: {error}')
        raise error

def send_facebook_messages(config, log_callback=None, progress_callback=None):
    """
    Main function to send Facebook messages
    
    Args:
        config: Dictionary with keys - cookies, delay, haters_name, chat_id, messages
        log_callback: Function to handle log messages (optional)
        progress_callback: Function to update message count (optional)
    
    Returns:
        int: Number of messages sent
    """
    global message_rotation_index
    message_rotation_index = 0
    
    driver = None
    message_count = 0
    should_stop = threading.Event()
    
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)
    
    try:
        log('Starting Facebook automation...')
        driver = setup_browser(log_callback)
        
        # Navigate to Facebook
        log('Navigating to Facebook...')
        driver.get('https://www.facebook.com/')
        time.sleep(8)
        
        # Add cookies if available
        cookie_string = config.get('cookies', '')
        if cookie_string and cookie_string.strip():
            log('Adding cookies to session...')
            cookie_array = cookie_string.split(';')
            cookies_added = 0
            
            for cookie in cookie_array:
                cookie_trimmed = cookie.strip()
                if cookie_trimmed:
                    first_equal_index = cookie_trimmed.find('=')
                    if first_equal_index > 0:
                        name = cookie_trimmed[:first_equal_index].strip()
                        value = cookie_trimmed[first_equal_index + 1:].strip()
                        try:
                            driver.add_cookie({
                                'name': name,
                                'value': value,
                                'domain': '.facebook.com',
                                'path': '/'
                            })
                            cookies_added += 1
                        except Exception:
                            pass
            log(f'{cookies_added} cookies added')
        
        # Navigate to conversation
        chat_id = config.get('chat_id', '')
        if chat_id and chat_id.strip():
            log(f'Opening conversation: {chat_id}')
            driver.get(f'https://www.facebook.com/messages/t/{chat_id}')
        else:
            log('No chat_id provided, opening messages page')
            driver.get('https://www.facebook.com/messages')
        
        time.sleep(12)
        
        # Find message input
        message_input = find_message_input(driver, log_callback)
        
        if not message_input:
            log('❌ Message input not found!')
            return 0
        
        log('✅ Message input found! Starting message loop...')
        
        # Get config values
        delay = random.randint(30, 90)
        haters_name = config.get('haters_name', '')
        messages = config.get('messages', ['Hello!'])
        
        # Message sending loop
        while not should_stop.is_set():
            try:
                base_message = get_next_message(messages)
                
                if haters_name and haters_name.strip():
                    message_to_send = f'{haters_name} {base_message}'
                else:
                    message_to_send = base_message
                
                log(f'Sending message {message_count + 1}: {message_to_send[:50]}...')
                
                # Type message using JavaScript
                driver.execute_script("""
                    const element = arguments[0];
                    const message = arguments[1];
                    
                    element.scrollIntoView({behavior: 'smooth', block: 'center'});
                    element.focus();
                    element.click();
                    
                    if (element.tagName === 'DIV') {
                        element.textContent = message;
                        element.innerHTML = message;
                    } else {
                        element.value = message;
                    }
                    
                    element.dispatchEvent(new Event('input', { bubbles: true }));
                    element.dispatchEvent(new Event('change', { bubbles: true }));
                """, message_input, message_to_send)
                
                time.sleep(2)
                
                # Send message (try button first, then Enter key)
                send_success = driver.execute_script("""
                    const sendButtons = document.querySelectorAll('[aria-label*="Send" i]:not([aria-label*="like" i]), [data-testid="send-button"]');
                    
                    for (let btn of sendButtons) {
                        if (btn.offsetParent !== null) {
                            btn.click();
                            return 'button_clicked';
                        }
                    }
                    return 'button_not_found';
                """)
                
                if send_success == 'button_not_found':
                    log('Send button not found, using Enter key...')
                    driver.execute_script("""
                        const element = arguments[0];
                        element.focus();
                        
                        const event = new KeyboardEvent('keydown', {
                            key: 'Enter',
                            code: 'Enter',
                            keyCode: 13,
                            which: 13,
                            bubbles: true
                        });
                        element.dispatchEvent(event);
                    """, message_input)
                else:
                    log('Send button clicked')
                
                time.sleep(2)
                
                message_count += 1
                if progress_callback:
                    progress_callback(message_count)
                
                log(f'✅ Message {message_count} sent successfully!')
                
                # Wait before next message
                time.sleep(delay)
                
            except Exception as e:
                log(f'Error in message loop: {str(e)}')
                # Try to recover
                try:
                    message_input = find_message_input(driver, log_callback)
                    if not message_input:
                        break
                except:
                    break
        
        log(f'🎉 Automation completed! Total messages sent: {message_count}')
        return message_count
        
    except Exception as error:
        log(f'❌ Fatal error: {error}')
        return message_count
    finally:
        if driver:
            try:
                driver.quit()
                log('Browser closed')
            except Exception:
                pass


# Function to run automation from database config (for Streamlit integration)
def run_automation_from_db_config(user_config, log_callback=None, progress_callback=None):
    """
    Run automation using config from database
    
    Args:
        user_config: Dictionary from database.get_user_config()
        log_callback: Function to handle log messages
        progress_callback: Function to update message count
    
    Returns:
        int: Number of messages sent
    """
    # Convert database config to automation engine format
    automation_config = {
        'cookies': user_config.get('cookies', ''),
        'delay': str(user_config.get('delay', 30)),
        'haters_name': user_config.get('name_prefix', ''),
        'chat_id': user_config.get('chat_id', ''),
        'messages': user_config.get('messages_file_content', '').split('\n') if user_config.get('messages_file_content') else ['Hello!']
    }
    
    # Filter out empty messages
    automation_config['messages'] = [msg.strip() for msg in automation_config['messages'] if msg.strip()]
    
    if not automation_config['messages']:
        automation_config['messages'] = ['Hello! Default message']
    
    return send_facebook_messages(automation_config, log_callback, progress_callback)
