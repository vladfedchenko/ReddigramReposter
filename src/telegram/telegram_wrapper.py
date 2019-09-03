"""
A module containing an object that wraps the C td_json_client object and provides a Python interface to access some of
its methods.
"""
from ctypes.util import find_library
from ctypes import *
from enum import Enum
import json
import logging
import os
import platform
import threading
from typing import List, Tuple, Callable


def on_fatal_error_callback(error_message: str):
    """A function to handle TDLib JSON library fatal errors

    Args:
        error_message: Received error message.
    """
    logging.critical(f"TDLib JSON library returned with an error: {error_message}.")


class TelegramAuthError(Exception):
    """Error raised in case of Telegram authentication error"""


class TelegramAuthState(Enum):
    """Authentication states for TelegramWrapper object"""
    WAIT_REQUEST = 0
    WAIT_TDLIB_PARAMETERS = 1
    WAIT_ENCRYPTION_KEY = 2
    WAIT_PHONE_NUMBER = 3
    WAIT_MFA_CODE = 4
    WAIT_PASSWORD = 5
    READY = 6


class TelegramAlbumMediaType(Enum):
    """Media types supported in album messages
    """
    IMAGE = 1
    VIDEO = 2


class TelegramMediaType(Enum):
    """Media types supported in media messages
    """
    IMAGE = TelegramAlbumMediaType.IMAGE
    VIDEO = TelegramAlbumMediaType.VIDEO
    ANIMATION = 3
    DOCUMENT = 4
    AUDIO = 5


class TelegramWrapper:
    """Object to access td_json_client methods via Python code.
    """

    def _init_log_handling(self, tdlib_log_verbosity: int, tdlib_log_file: str, tdlib_log_max_size: int):
        result = self._td_client_execute({'@type': 'setLogVerbosityLevel',
                                          'new_verbosity_level': tdlib_log_verbosity})
        if result and result['@type'] == 'ok':
            logging.info(f"TDLib JSON log verbosity changed to {tdlib_log_verbosity}.")
        else:
            logging.warning(f"TDLib JSON log verbosity change not confirmed.")

        if tdlib_log_file is not None:
            log_stream_file = {'@type': 'logStreamFile', 'path': tdlib_log_file, 'max_file_size': tdlib_log_max_size}
            result = self._td_client_execute({'@type': 'setLogStream',
                                              'log_stream': log_stream_file})
            if result and result['@type'] == 'ok':
                logging.info(f"TDLib JSON log location changed to {tdlib_log_file}.")
            else:
                logging.warning(f"TDLib JSON log location change not confirmed.")

    def _init_native_funcs(self, tdjson):
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

    @staticmethod
    def _get_media_fie_content(media_path: str, media_type: TelegramMediaType, caption: str = ""):
        media = {'@type': 'inputFileLocal', 'path': media_path}
        if media_type == TelegramMediaType.ANIMATION:
            content = {'@type': 'inputMessageAnimation', 'animation': media, 'caption': {'text': caption}}
        elif media_type == TelegramMediaType.IMAGE:
            content = {'@type': 'inputMessagePhoto', 'photo': media, 'caption': {'text': caption}}
        elif media_type == TelegramMediaType.DOCUMENT:
            content = {'@type': 'inputMessageDocument', 'document': media, 'caption': {'text': caption}}
        elif media_type == TelegramMediaType.AUDIO:
            content = {'@type': 'inputMessageAudio', 'audio': media, 'caption': {'text': caption}}
        else:
            content = {'@type': 'inputMessageVideo',
                       'video': media,
                       'caption': {'text': caption},
                       'supports_streaming': True}
        return content

    def _notify_message_sent(self, message: dict):
        logging.debug(f"Message sent: {message}")
        for callback in self._message_sent_callbacks:
            callback(message)
        logging.debug(f"Message sent: All subscribers notified.")

    def _process_authorization(self, auth_state: dict):
        if auth_state['@type'] == 'authorizationStateWaitTdlibParameters':
            logging.debug("Waiting TDLib parameters.")
            self._auth_state = TelegramAuthState.WAIT_TDLIB_PARAMETERS

        elif auth_state['@type'] == 'authorizationStateWaitEncryptionKey':
            logging.debug("Waiting TDLib encryption key.")
            self._auth_state = TelegramAuthState.WAIT_ENCRYPTION_KEY
            self._td_client_send({'@type': 'checkDatabaseEncryptionKey', 'key': 'my_key'})

        elif auth_state['@type'] == 'authorizationStateWaitPhoneNumber':
            logging.debug("Waiting TDLib phone number.")
            self._auth_state = TelegramAuthState.WAIT_PHONE_NUMBER

        elif auth_state['@type'] == 'authorizationStateWaitCode':
            logging.debug("Waiting TDLib MFA code.")
            self._auth_state = TelegramAuthState.WAIT_MFA_CODE

        elif auth_state['@type'] == 'authorizationStateWaitPassword':
            logging.debug("Waiting TDLib password.")
            self._auth_state = TelegramAuthState.WAIT_PASSWORD

        elif auth_state['@type'] == 'authorizationStateReady':
            logging.info("TelegramWrapper ready!")
            self._auth_state = TelegramAuthState.READY

    def _td_client_execute(self, query):
        query = json.dumps(query).encode('utf-8')
        result = self._client_execute(self._client, query)
        if result:
            result = json.loads(result.decode('utf-8'))
        return result

    def _td_client_receive(self):
        result = self._client_receive(self._client, 1.0)
        if result:
            result = json.loads(result.decode('utf-8'))
        return result

    def _td_client_send(self, query):
        query = json.dumps(query).encode('utf-8')
        self._client_send(self._client, query)

    def _td_receive_handler(self):
        logging.debug(f"TDLib JSON message receiver thread started.")
        while not self._receive_handler_stop.is_set():
            event = self._td_client_receive()

            if event:
                # In the next section all of incoming messages should be processed
                # print(event)
                if event['@type'] == 'updateNewChat':
                    chat_title = event['chat']['title']
                    chat_id = event['chat']['id']
                    logging.debug(f"TDLib JSON: chat ID saved: {chat_title}:{chat_id}")
                    with self._chat_id_map_lock:
                        self._chat_id_map[chat_title] = chat_id

                elif event['@type'] == 'updateMessageSendSucceeded':
                    self._notify_message_sent(event['message'])

                elif event['@type'] == 'updateAuthorizationState':
                    self._process_authorization(event['authorization_state'])

                elif event['@type'] == 'error':
                    logging.error(f'Telegram error received: {event["code"]} - {event["message"]}')

    def __del__(self):
        logging.debug(f"Deleting TelegramWrapper object.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __init__(self,
                 tdlib_log_verbosity: int = 0,
                 tdlib_log_file: str = None,
                 tdlib_log_max_size: int = 10):
        """Initialize TelegramWrapper object.

        Args:

            tdlib_allow_input: If True - user will be able to enter authentication info through the console.
                If False - authentication info is retrieved from tdlib_auth_info dictionary.
                Note: if MFA is enabled the input of authentication code is expected on first login.
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

        self._init_native_funcs(tdjson)

        # Error callback handling
        fatal_error_callback_type = CFUNCTYPE(None, c_char_p)
        td_set_log_fatal_error_callback = tdjson.td_set_log_fatal_error_callback
        td_set_log_fatal_error_callback.restype = None
        td_set_log_fatal_error_callback.argtypes = [fatal_error_callback_type]
        c_on_fatal_error_callback = fatal_error_callback_type(on_fatal_error_callback)
        td_set_log_fatal_error_callback(c_on_fatal_error_callback)

        self._client = self._client_create()
        logging.info("TDLib JSON client created.")

        self._init_log_handling(tdlib_log_verbosity, tdlib_log_file, tdlib_log_max_size)

        self._auth_state = TelegramAuthState.WAIT_REQUEST

        logging.debug(f"Telegram wrapper callback lists initialization.")
        self._message_sent_callbacks = set()
        logging.debug(f"Telegram wrapper callback lists initialization finished.")

        # Keep this section last. New thread may start using resources which are not initialized yet otherwise.
        logging.info(f"TDLib JSON message receiver thread initialization.")
        self._chat_id_map = {}
        self._chat_id_map_lock = threading.Lock()
        self._receive_handler_stop = threading.Event()
        self._receive_handler_thread = threading.Thread(target=self._td_receive_handler, args=())
        self._receive_handler_thread.start()
        logging.info(f"TDLib JSON message receiver thread initialization finished.")

    # Public methods
    @property
    def authentication_state(self) -> TelegramAuthState:
        """Returns the authentication state ot the wrapper"""
        return self._auth_state

    @staticmethod
    def determine_media_type(file_path: str) -> TelegramMediaType:
        """Determine the type of media of a file based on its extension.

        Args:
            file_path: Path to media file.
        Returns:
            TelegramMediaType: Media type based on file extension. If extension not recognized - DOCUMENT type returned.
        """
        ext = os.path.splitext(file_path)[1][1:]
        ret_type = TelegramMediaType.DOCUMENT
        if ext == 'gif':
            ret_type = TelegramMediaType.ANIMATION
        elif ext == 'jpg' or ext == 'png':
            ret_type = TelegramMediaType.IMAGE
        elif ext == 'mp4' or ext == 'avi' or ext == 'webm':
            ret_type = TelegramMediaType.VIDEO
        return ret_type

    def send_album_message(self, media_list: List[Tuple[str, TelegramAlbumMediaType, str]], **kwargs) -> bool:
        """Send an media album message to a chat specified by either a chat id or chat title.

        Args:
            media_list: A list of media files. Each media file is a Tuple consisting of path, media type and a caption.
            **chat_id (int): ID of the target chat.
            **chat_title (str): Title of the target chat.
                Use this option only after executing update_chat_ids at least once.
        Returns:
            bool: True if the message is sent. False otherwise. Delivery is not guaranteed.
        """
        chat_id = None
        if 'chat_id' in kwargs:
            chat_id = kwargs['chat_id']
        elif 'chat_title' in kwargs:
            with self._chat_id_map_lock:
                if kwargs['chat_title'] in self._chat_id_map:
                    chat_id = self._chat_id_map[kwargs['chat_title']]

        if chat_id is not None:
            logging.debug(f"Sending the album message of {len(media_list)} entities to chat id {chat_id}.")
            contents = [TelegramWrapper._get_media_fie_content(x[0], TelegramMediaType(x[1]), x[2]) for x in media_list]
            self._td_client_send({'@type': 'sendMessageAlbum', 'chat_id': chat_id, 'input_message_contents': contents})
            return True
        else:
            return False

    def send_media_message(self,
                           media_path: str,
                           media_type: TelegramMediaType = TelegramMediaType.IMAGE,
                           **kwargs) -> bool:
        """Send a media message to a chat specified by either a chat id or chat title.

        Args:
            media_path: Path to a media file.
            media_type: Type of media file.
            **caption (str): Caption for an image.
            **chat_id (int): ID of the target chat.
            **chat_title (str): Title of the target chat.
                Use this option only after executing update_chat_ids at least once.
        Returns:
            bool: True if the message is sent. False otherwise. Delivery is not guaranteed.
        """
        chat_id = None
        if 'chat_id' in kwargs:
            chat_id = kwargs['chat_id']
        elif 'chat_title' in kwargs:
            with self._chat_id_map_lock:
                if kwargs['chat_title'] in self._chat_id_map:
                    chat_id = self._chat_id_map[kwargs['chat_title']]

        if chat_id is not None:
            logging.debug(f"Sending the next media message: {media_path} to chat id {chat_id}.")
            caption_text = kwargs['caption'] if 'caption' in kwargs else ''
            content = TelegramWrapper._get_media_fie_content(media_path, media_type, caption_text)
            self._td_client_send({'@type': 'sendMessage', 'chat_id': chat_id, 'input_message_content': content})
            return True
        else:
            return False

    def send_text_message(self, text: str, **kwargs) -> bool:
        """Send a text message to a chat specified by either a chat id or chat title.

        Args:
            text: Text to send.
            **chat_id (int): ID of the target chat.
            **chat_title (str): Title of the target chat.
                Use this option only after executing update_chat_ids at least once.
        Returns:
            bool: True if the message is sent. False otherwise. Delivery is not guaranteed.
        """
        chat_id = None
        if 'chat_id' in kwargs:
            chat_id = kwargs['chat_id']
        elif 'chat_title' in kwargs:
            with self._chat_id_map_lock:
                if kwargs['chat_title'] in self._chat_id_map:
                    chat_id = self._chat_id_map[kwargs['chat_title']]

        if chat_id is not None:
            logging.debug(f"Sending the next text message: {text} to chat id {chat_id}.")
            content = {'@type': 'inputMessageText', 'text': {'text': text}}
            self._td_client_send({'@type': 'sendMessage', 'chat_id': chat_id, 'input_message_content': content})
            return True
        else:
            return False

    def set_tdlib_parameters(self, api_id: int, api_hash: str, tdlib_database_directory: str = 'tdlib_db'):
        """Set TDLib parameters for client authentication.
        Execute only if authentication state is WAIT_TDLIB_PARAMETERS.

        Args:
            api_id: TDLib api ID. Can be obtained at https://my.telegram.org.
            api_hash: TDLib api hash. Can be obtained at https://my.telegram.org.
            tdlib_database_directory: Location of the directory to store TDLib data.
        Raises:
            TelegramAuthError: If wrapper is not expecting TDLib parameters now.
        """
        if self._auth_state == TelegramAuthState.WAIT_TDLIB_PARAMETERS:
            logging.debug(f"TDLib JSON sending parameters.")
            self._td_client_send({'@type': 'setTdlibParameters', 'parameters': {
                                  'database_directory': tdlib_database_directory,
                                  'api_id': api_id,
                                  'api_hash': api_hash,
                                  'system_language_code': 'en',
                                  'device_model': 'Desktop',
                                  'system_version': 'Linux',
                                  'application_version': '0.1',
                                  'enable_storage_optimizer': True}})
            self._auth_state = TelegramAuthState.WAIT_REQUEST

        else:
            logging.error(f"TDLib JSON not expecting TDLib parameters now.")
            raise TelegramAuthError("Not expecting TDLib parameters now.")

    def set_tdlib_phone(self, phone: str):
        """Set TDLib phone number for client authentication.
        Execute only if authentication state is WAIT_PHONE_NUMBER.

        Args:
            phone: Telegram phone number.
        Raises:
            TelegramAuthError: If wrapper is not expecting phone number now.
        """
        if self._auth_state == TelegramAuthState.WAIT_PHONE_NUMBER:
            logging.debug(f"TDLib JSON sending phone number.")
            self._td_client_send({'@type': 'setAuthenticationPhoneNumber', 'phone_number': phone})
            self._auth_state = TelegramAuthState.WAIT_REQUEST
        else:
            logging.error(f"TDLib JSON not expecting phone number now.")
            raise TelegramAuthError("Not expecting phone number now.")

    def set_tdlib_mfa_code(self, code: str):
        """Set TDLib MFA code for client authentication.
        Execute only if authentication state is WAIT_MFA_CODE.

        Args:
            code: Telegram MFA code.
        Raises:
            TelegramAuthError: If wrapper is not expecting MFA code now.
        """
        if self._auth_state == TelegramAuthState.WAIT_MFA_CODE:
            logging.debug(f"TDLib JSON sending MFA code.")
            self._td_client_send({'@type': 'checkAuthenticationCode', 'code': code})
            self._auth_state = TelegramAuthState.WAIT_REQUEST
        else:
            logging.error(f"TDLib JSON not expecting MFA code now.")
            raise TelegramAuthError("Not expecting MFA code now.")

    def set_tdlib_password(self, password: str):
        """Set TDLib password for client authentication.
        Execute only if authentication state is WAIT_MFA_CODE.

        Args:
            password: Telegram password.
        Raises:
            TelegramAuthError: If wrapper is not expecting password now.
        """
        if self._auth_state == TelegramAuthState.WAIT_PASSWORD:
            logging.debug(f"TDLib JSON sending password.")
            self._td_client_send({'@type': 'checkAuthenticationPassword', 'password': password})
            self._auth_state = TelegramAuthState.WAIT_REQUEST
        else:
            logging.error(f"TDLib JSON not expecting password now.")
            raise TelegramAuthError("Not expecting password now.")

    def stop(self):
        """Stop all internal threads. Needed for garbage collection"""
        logging.debug(f"Stopping TelegramWrapper object.")
        if self._receive_handler_stop is not None:
            self._receive_handler_stop.set()
            self._receive_handler_thread.join()
            self._receive_handler_stop = None
            self._receive_handler_thread = None

    def subscribe_message_sent(self, callback: Callable[[dict], None]):
        """Subscribe to receive confirmations that the message has been sent.

        Args:
            callback: Callback function. The message will be passed as an argument when calling the callback.
        """
        if callback not in self._message_sent_callbacks:
            self._message_sent_callbacks.add(callback)

    def unsubscribe_message_sent(self, callback: Callable[[dict], None]):
        """Unsubscribe from receiving confirmations that the message has been sent.

        Args:
            callback: Callback function previously passed to subscribe_message_sent.
        """
        if callback in self._message_sent_callbacks:
            self._message_sent_callbacks.remove(callback)

    def update_chat_ids(self, limit: int = 1000):
        """Update the list of chat IDs. It is needed for successful send_text_message execution with only chat title
        specified.

        Args:
            limit: Max number of chats to be received. Most recent chats will be received.
        """
        self._td_client_send({'@type': 'getChats', 'limit': limit})
