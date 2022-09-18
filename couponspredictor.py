import datetime
import calendar
from dataclasses import dataclass
from dataclasses import field
import config

import telegram
from telegram.ext import Updater

import tinkoff.invest as t_invest

TOKEN = config.TELEGRAM_BOT_TOKEN

updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher

import logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

def start(update, context):
    # `update.effective_chat.id` - определяем `id` чата, 
    # откуда прилетело сообщение 

    ololo = ''
    with t_invest.Client(config.TINKOFF_INVEST_TOKEN) as client:
        ololo = client.users.get_accounts().accounts
        for account in ololo:    
            replay_string = f"{account.name}\n"

            portfolio = client.operations.get_portfolio(account_id=account.id)
            bonds_figi = []
            for instrument in portfolio.positions:
                if instrument.instrument_type == "bond":
                    bonds_figi.append(instrument.figi)

            if not bonds_figi:
                continue

            today = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
            days = calendar.monthrange(today.year, today.month)[1]
            next_month_date = today + datetime.timedelta(days=days)

            
            @dataclass(order=True)
            class BondCoupon:
                figi: str = field(compare=False)
                name: str = field(compare=False)
                coupon_date: datetime.date = field(compare=True)
                pay_one_bond: t_invest.MoneyValue = field(compare=False)
                quantity: int = field(compare=False)

            bond_coupons = list[BondCoupon]()

            for bond_figi in bonds_figi:
                bond = client.instruments.bond_by(id_type=t_invest.InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI, id=bond_figi)
                bond_coupons_info = client.instruments.get_bond_coupons(figi=bond_figi, from_=today, to=next_month_date)
                
                quantity = t_invest.Quotation()

                for instrument_pos in portfolio.positions:
                    if instrument_pos.instrument_type == "bond" and instrument_pos.figi == bond_figi:
                        quantity = instrument_pos.quantity.units

                for bond_coupon_info in bond_coupons_info.events:
                    bond_coupons.append(BondCoupon(bond_figi, bond.instrument.name, bond_coupon_info.coupon_date.date(), bond_coupon_info.pay_one_bond, quantity))

            bond_coupons = sorted(bond_coupons)

            for bond_coupon in bond_coupons:
                pay_one_bond = bond_coupon.pay_one_bond.units + bond_coupon.pay_one_bond.nano / 10e8
                replay_string += f"\t*{bond_coupon.coupon_date}:* {bond_coupon.name} \
                                    {bond_coupon.quantity} \* {pay_one_bond} = *{(bond_coupon.quantity * pay_one_bond):.2f} {bond_coupon.pay_one_bond.currency}*\n"

            context.bot.send_message(
                chat_id=update.effective_chat.id, text=replay_string, parse_mode=telegram.ParseMode.MARKDOWN)

# импортируем обработчик CommandHandler, 
# который фильтрует сообщения с командами
from telegram.ext import CommandHandler
# если увидишь команду `/start`,
# то вызови функцию `start()`
start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

updater.start_polling()