"""
A module containing an object that wraps the C td_json_client object and provides a Python interface to access some of
its methods.
"""
from ctypes.util import find_library
from ctypes import *
import json
import logging
import os
import platform
import time


def on_fatal_error_callback(error_message: str):
    """A function to handle TDLib JSON library fatal errors

    Args:
        error_message: Received error message.
    """
    logging.critical(f"TDLib JSON library returned with an error: {error_message}.")


class TelegramAuthError(Exception):
    """Error raised in case of Telegram authentication error"""


class TelegramWrapper:
    """Object to access td_json_client methods via Python code.
    """
    _client_create = None
    _client_receive = None
    _client_send = None
    _client_execute = None
    _client_destroy = None

    _client = None

    def _td_client_send(self, query):
        query = json.dumps(query).encode('utf-8')
        self._client_send(self._client, query)

    def _td_client_receive(self):
        result = self._client_receive(self._client, 1.0)
        if result:
            result = json.loads(result.decode('utf-8'))
        return result

    def _td_client_execute(self, query):
        query = json.dumps(query).encode('utf-8')
        result = self._client_execute(self._client, query)
        if result:
            result = json.loads(result.decode('utf-8'))
        return result

    def __init__(self,
                 tdlib_api_id: int,
                 tdlib_api_hash: str,
                 tdlib_allow_input: bool = True,
                 tdlib_auth_info: map = None,
                 tdlib_database_directory: str = "tdlib_db",
                 tdlib_auth_timeout: int = 10,
                 tdlib_log_verbosity: int = 0,
                 tdlib_log_file: str = None,
                 tdlib_log_max_size: int = 10):
        """Initialize TelegramWrapper object.

        Args:
            tdlib_api_id: Application identifier for Telegram API access, which can be obtained
                at https://my.telegram.org.
            tdlib_api_hash: Application identifier hash for Telegram API access, which can be obtained
                at https://my.telegram.org.
            tdlib_allow_input: If True - user will be able to enter authentication info through the console.
                If False - authentication info is retrieved from tdlib_auth_info dictionary.
                Note: if MFA is enabled the input of authentication code is expected on first login.
            tdlib_auth_info: Dictionary of authentication parameters.
                Expected to contain 'phone' and 'password' key-value pairs.
            tdlib_database_directory: Location of the directory to store TDLib data.
            tdlib_auth_timeout: Amount of time in seconds to wait for authentication confirmation.
            tdlib_log_verbosity: Log verbosity level for TDLib JSON library. Range: [0-5+].
            tdlib_log_file: TDLib JSON library log file location.
            tdlib_log_max_size: TDLib JSON library log file max size (in MB).

        Raises:
            ModuleNotFoundError: Cannot locate the TDLib JSON library.
            TelegramAuthError: Authentication error encountered.
        """
        module_dir = os.path.dirname(__file__)
        tdjson_path = find_library('tdjson') or f"{module_dir}/lib/{platform.uname()[4]}/libtdjson.so"
        logging.debug(f"Loading TDLib JSON with this location: {tdjson_path}")

        if tdjson_path is None:
            logging.critical("TDLib JSON library not found. Cannot initialize TelegramWrapper object.")
            raise ModuleNotFoundError("TDLib JSON library not found. Cannot initialize TelegramWrapper object.")
        tdjson = CDLL(tdjson_path)
        logging.info("TDLib JSON lib loaded successfully.")

        self._client_create = tdjson.td_json_client_create
        self._client_create.restype = c_void_p
        self._client_create.argtypes = []

        self._client_receive = tdjson.td_json_client_receive
        self._client_receive.restype = c_char_p
        self._client_receive.argtypes = [c_void_p, c_double]

        self._client_send = tdjson.td_json_client_send
        self._client_send.restype = None
        self._client_send.argtypes = [c_void_p, c_char_p]

        self._client_execute = tdjson.td_json_client_execute
        self._client_execute.restype = c_char_p
        self._client_execute.argtypes = [c_void_p, c_char_p]

        self._client_destroy = tdjson.td_json_client_destroy
        self._client_destroy.restype = None
        self._client_destroy.argtypes = [c_void_p]

        # Error callback handling
        fatal_error_callback_type = CFUNCTYPE(None, c_char_p)
        td_set_log_fatal_error_callback = tdjson.td_set_log_fatal_error_callback
        td_set_log_fatal_error_callback.restype = None
        td_set_log_fatal_error_callback.argtypes = [fatal_error_callback_type]
        c_on_fatal_error_callback = fatal_error_callback_type(on_fatal_error_callback)
        td_set_log_fatal_error_callback(c_on_fatal_error_callback)

        # setting low verbosity level before client is created
        result = self._td_client_execute({'@type': 'setLogVerbosityLevel',
                                          'new_verbosity_level': 0})

        self._client = self._client_create()
        logging.info("TDLib JSON client created.")

        # TDLib JSON logging handling
        result = self._td_client_execute({'@type': 'setLogVerbosityLevel',
                                          'new_verbosity_level': tdlib_log_verbosity})
        if result and result['@type'] == 'ok':
            logging.info(f"TDLib JSON log verbosity changed to {tdlib_log_verbosity}.")
        else:
            logging.warning(f"TDLib JSON log verbosity change not confirmed.")

        if tdlib_log_file is not None:
            # TODO: This part is not working! Fix later.
            log_stream_file = {'@type': 'logStreamFile', 'path_': tdlib_log_file, 'max_file_size_': tdlib_log_max_size}
            result = self._td_client_execute({'@type': 'setLogStream',
                                              'log_stream_': log_stream_file})
            if result and result['@type'] == 'ok':
                logging.info(f"TDLib JSON log location changed to {log_stream_file}.")
            else:
                logging.warning(f"TDLib JSON log location change not confirmed.")

        # TDLib JSON authentication handling
        logging.debug(f"TDLib JSON authentication stage started.")
        countdown_start = time.time()
        authenticated = False
        while time.time() - countdown_start <= tdlib_auth_timeout:
            event = self._td_client_receive()

            if event and event['@type'] == 'updateAuthorizationState':
                auth_state = event['authorization_state']

                if auth_state['@type'] == 'authorizationStateWaitTdlibParameters':
                    self._td_client_send({'@type': 'setTdlibParameters', 'parameters': {
                                              'database_directory': tdlib_database_directory,
                                              'api_id': tdlib_api_id,
                                              'api_hash': tdlib_api_hash,
                                              'system_language_code': 'en',
                                              'device_model': 'Desktop',
                                              'system_version': 'Linux',
                                              'application_version': '0.1',
                                              'enable_storage_optimizer': True}})

                if auth_state['@type'] == 'authorizationStateWaitEncryptionKey':
                    self._td_client_send({'@type': 'checkDatabaseEncryptionKey', 'key': 'my_key'})

                if auth_state['@type'] == 'authorizationStateWaitPhoneNumber':
                    if tdlib_auth_info is not None and 'phone' in tdlib_auth_info:
                        phone_number = tdlib_auth_info['phone']
                    elif tdlib_allow_input:
                        phone_number = input('Please insert your phone number: ')
                        countdown_start = time.time()  # countdown is reset if user input is expected
                    else:
                        logging.error("TDLib JSON: phone number is requested but not provided.")
                        raise TelegramAuthError("TDLib JSON: phone number is requested but not provided.")

                    self._td_client_send({'@type': 'setAuthenticationPhoneNumber', 'phone_number': phone_number})

                if auth_state['@type'] == 'authorizationStateWaitCode':
                    if tdlib_allow_input:
                        code = input('Please insert the authentication code you received: ')
                        countdown_start = time.time()  # countdown is reset if user input is expected
                    else:
                        logging.error("TDLib JSON: authentication code is requested but not provided.")
                        raise TelegramAuthError("TDLib JSON: authentication code is requested but not provided.")
                    self._td_client_send({'@type': 'checkAuthenticationCode', 'code': code})

                if auth_state['@type'] == 'authorizationStateWaitPassword':
                    if tdlib_auth_info is not None and 'password' in tdlib_auth_info:
                        password = tdlib_auth_info['password']
                    elif tdlib_allow_input:
                        password = input('Please insert your password: ')
                        countdown_start = time.time()  # countdown is reset if user input is expected
                    else:
                        logging.error("TDLib JSON: password is requested but not provided.")
                        raise TelegramAuthError("TDLib JSON: password is requested but not provided.")

                    self._td_client_send({'@type': 'checkAuthenticationPassword', 'password': password})

                if auth_state['@type'] == 'authorizationStateReady':
                    authenticated = True
                    logging.info(f"TDLib JSON client authenticated.")
                    break

        if not authenticated:
            logging.error("TDLib JSON client authentication unknown error.")
            raise TelegramAuthError("TDLib JSON client authentication unknown error.")
