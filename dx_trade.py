import posixpath
import requests
from time import sleep
from uuid import uuid4

from utils import get_logger


class DXTrade:
    def __init__(self, username, password, api_url, domain='default'):
        self.api_url = api_url
        self.username = username
        self.domain = domain
        self.password = password
        self.logger = get_logger(__class__.__name__)
        # generated data
        self.session_token = None
        self.session_token_expiration = None
        self.account = None
        self.accounts = []

    def _place_request(self, request_type, url, headers=None, json_data=None, max_iterations=3):
        if request_type == "GET":
            response = requests.get(url, headers=headers)
        elif request_type == "PUT":
            response = requests.put(url, headers=headers, json=json_data)
        elif request_type == "POST":
            response = requests.post(url, headers=headers, json=json_data)
        elif request_type == "DELETE":
            response = requests.delete(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            if max_iterations:
                sleep(1)
                return self._place_request(
                    request_type=request_type,
                    url=url,
                    headers=headers,
                    json_data=json_data,
                    max_iterations=max_iterations-1
                )
            else:
                self.logger.error("Max iterations reached")
        return {}

    def login(self):
        url = posixpath.join(self.api_url, 'login')
        data = {
            "username": self.username,
            "domain": self.domain,
            "password": self.password
        }
        response_data = self._place_request('POST', url=url, json_data=data)
        if 'errorCode' in response_data:
            self.logger.error(f"Login error: {response_data}")
        else:
            self._update_session_token(
                session_token=response_data['sessionToken'],
                timeout=response_data['timeout']
            )
            self.logger.info(f"Login: {response_data}")
        return response_data

    def _update_session_token(self, session_token, timeout):
        self.session_token = session_token
        # timeout tbd

    def _authorisation_add_header(self, headers=None):
        if not headers:
            headers = {"Authorization": f"DXAPI {self.session_token}"}
        else:
            headers["Authorization"] = f"DXAPI {self.session_token}"
        return headers

    def get_user_info(self):
        url = posixpath.join(self.api_url, "users", self.username)
        headers = self._authorisation_add_header()
        response_data = self._place_request(request_type="GET", url=url, headers=headers)
        self.logger.info(f"GetUserInfo: {response_data}")
        return response_data

    def get_accounts(self):
        user_info = self.get_user_info()
        user_details = user_info.get('userDetails')[0]
        if user_details and 'accounts' in user_details:
            accounts = user_details.get('accounts')
            self.accounts = [account['account'] for account in accounts]
            self.logger.info(f"Accounts: {accounts}")
            return accounts
        return []

    def place_limit_order(
            self, account, limit_type, instrument, quantity, side, limit_price,
            position_effect=None, position_code=None
    ):
        order_code = f'unique_{str(uuid4())}'
        data = {
            "orderCode": order_code,
            "type": limit_type,
            "instrument": instrument,
            "quantity": quantity,
            "positionEffect": position_effect,
            "positionCode": position_code,
            "side": side,
            "limitPrice": limit_price,
            "tif": "GTC"
        }
        url = posixpath.join(self.api_url, "accounts", account, "orders")
        headers = self._authorisation_add_header()
        response_data = self._place_request(
            request_type="POST", url=url, headers=headers, json_data=data
        )
        return response_data.get('orderId'), order_code

    def place_stop_order(
            self, account, limit_type, instrument, quantity, side, stop_price,
            position_effect=None, position_code=None
    ):
        order_code = f'unique_{str(uuid4())}'
        data = {
            "orderCode": order_code,
            "type": limit_type,
            "instrument": instrument,
            "quantity": quantity,
            "positionEffect": position_effect,
            "positionCode": position_code,
            "side": side,
            "stopPrice": stop_price,
            "tif": "GTC"
        }
        url = posixpath.join(self.api_url, "accounts", account, "orders")
        headers = self._authorisation_add_header()
        response_data = self._place_request(
            request_type="POST", url=url, headers=headers, json_data=data
        )
        return response_data.get('orderId'), order_code

    def place_market_order(
            self, account, instrument, quantity,  side, sl=None, tp=None
    ):
        self.logger.info('Place market order')
        order_code = f'unique_{str(uuid4())}'
        data = {
            "orderCode": order_code,
            "type": "MARKET",           # [MARKET, LIMIT, STOP]
            "instrument": instrument,   # XAUUSD
            "quantity": quantity,       # 1
            "positionEffect": "OPEN",   # [OPEN, CLOSE]
            "side": side,
            "tif": "GTC"                # [GTC, DAY, GTD]
        }
        url = posixpath.join(self.api_url, "accounts", account, "orders")
        headers = self._authorisation_add_header()
        response_data = self._place_request(
            request_type="POST", url=url, headers=headers, json_data=data
        )
        position_code = None
        tp_order_code = None
        sl_order_code = None
        if type(response_data) is dict and 'orderId' in response_data.keys():
            position_code = response_data['orderId']
            if position_code:
                if tp is not None:
                    tp_order_code = self.set_market_order_tp(
                        account=account,
                        instrument=instrument,
                        quantity=quantity,
                        side=side,
                        tp=tp,
                        position_code=position_code
                    )[1]
                if sl is not None:
                    sl_order_code = self.set_market_order_sl(
                        account=account,
                        instrument=instrument,
                        quantity=quantity,
                        side=side,
                        sl=sl,
                        position_code=position_code
                    )[1]
        self.logger.info(f"{position_code}, {tp_order_code}, {sl_order_code}")
        return position_code, tp_order_code, sl_order_code

    def set_market_order_tp(
            self, account, instrument, quantity, side, tp, position_code
    ):
        tp_position_code, tp_order_code = self.place_limit_order(
            account=account,
            limit_type='LIMIT',
            instrument=instrument,
            quantity=quantity,
            side='BUY' if side == 'SELL' else 'SELL',
            limit_price=tp,
            position_effect='CLOSE',
            position_code=position_code,
        )
        return tp_position_code, tp_order_code

    def set_market_order_sl(
            self, account, instrument, quantity, side, sl, position_code
    ):
        sl_position_code, sl_order_code = self.place_stop_order(
            account=account,
            limit_type='STOP',
            instrument=instrument,
            quantity=quantity,
            side='BUY' if side == 'SELL' else 'SELL',
            stop_price=sl,
            position_effect='CLOSE',
            position_code=position_code,
        )
        return sl_position_code, sl_order_code

    def cancel_order(self, account, order_code):
        url = posixpath.join(
            self.api_url, "accounts", account, "orders", order_code)
        headers = self._authorisation_add_header()
        self._place_request(
            request_type="DELETE", url=url, headers=headers)

    def list_open_orders(self, account_code):
        url = posixpath.join(self.api_url, "accounts", account_code, "orders")
        headers = self._authorisation_add_header()
        response_data = self._place_request(request_type="GET", url=url, headers=headers)
        orders = response_data['orders'] if 'orders' in response_data else []
        self.logger.info(f"ListOpenOrders: {orders}")
        return orders

    def list_open_positions(self, account_code):
        url = posixpath.join(self.api_url, "accounts", account_code, "positions")
        headers = self._authorisation_add_header()
        response_data = self._place_request(request_type="GET", url=url, headers=headers)
        positions = response_data['positions'] if 'positions' in response_data else []
        self.logger.info(f"ListOpenPositions: {response_data}")
        return positions

    def list_open_positions_sl_tp(self, account_code):
        open_positions = self.list_open_positions(account_code)
        open_orders = self.list_open_orders(account_code)
        for position in open_positions:
            position_code = position['positionCode']
            position_instrument = position['symbol']
            position_side = position['side']
            # iterate through open orders and fetch sl and tp
            for order in open_orders:
                # TP
                if (
                        order['type'] == 'LIMIT'
                        and order['legCount'] == 1
                        and order['instrument'] == position_instrument
                        and order['side'] != position_side
                ):
                    if order['legs'][0]['positionCode'] == position_code:
                        position['tpPositionCode'] = order['orderCode']
                        position['tpOrderCode'] = order['clientOrderId']
                        position['tpPrice'] = round(order['legs'][0]['price'], 5)
                elif (
                        order['type'] == 'STOP'
                        and order['legCount'] == 1
                        and order['instrument'] == position_instrument
                        and order['side'] != position_side
                ):
                    if order['legs'][0]['positionCode'] == position_code:
                        position['slPosition_code'] = order['orderCode']
                        position['slOrderCode'] = order['clientOrderId']
                        position['slPrice'] = round(order['legs'][0]['price'], 5)
        return open_positions


if __name__ == '__main__':
    obj = DXTrade(
        username="wWKcyZ",
        password="wPMwSuJh",
        api_url="https://demo.dx.trade/dxsca-web"

    )

    obj.login()
    obj.get_accounts()
    for account in obj.accounts:
        # place order with tp and sl
        print('Place order')
        position_code, tp_order_code, sl_order_code = obj.place_market_order(
            account=account,
            instrument='XAUUSD',
            quantity=1,
            side='BUY',
            tp=None,
            sl=None,
        )
        print(position_code, tp_order_code, sl_order_code)

        print('Place TP')
        tp_position_code, tp_order_code = obj.set_market_order_tp(
            account=account,
            instrument='XAUUSD',
            quantity=1,
            side='BUY',
            tp=2150,
            position_code=position_code
        )
        print(tp_position_code, tp_order_code)

        print('Cancel order')
        sleep(1)
        obj.cancel_order(account, tp_order_code)

        print('Place TP 2')
        tp_position_code, tp_order_code = obj.set_market_order_tp(
            account=account,
            instrument='XAUUSD',
            quantity=1,
            side='BUY',
            tp=2200,
            position_code=position_code
        )
        print(tp_position_code, tp_order_code)

        print('Open orders')
        open_orders = obj.list_open_orders(account)
        for open_order in open_orders:
            print(open_order)

        print('Open positions')
        open_positions = obj.list_open_positions(account)
        for open_position in open_positions:
            print(open_position)

        print('Open positions with tp and sl')
        open_positions = obj.list_open_positions_sl_tp(account)
        for open_position in open_positions:
            print(open_position)