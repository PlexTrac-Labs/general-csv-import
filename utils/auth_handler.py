import time
import argparse

import api
import utils.input_utils as input
import utils.log_handler as logger
log = logger.log

class Auth():
    
    def __init__(self, args:argparse.Namespace):
        self.base_url = args.instance_url
        self.username = args.username
        self.password = args.password
        self.tenant_id = None
        self.auth_headers = {}

        self.time_since_last_auth = None


    def add_auth_header(self, authorization_token):
        self.auth_headers["Authorization"] = authorization_token


    def get_auth_headers(self):
        """
        checks is authorization is current and returns headers, otherwise tries to re-authenticate and return new auth headers

        to prevent the auth from timing out after it was checked, but before it can be received by the API,
        checks whether we are in the last minute of the 15 min auth window
        """
        if self.time_since_last_auth == None:
            self.handle_authentication()
        elif time.time() - self.time_since_last_auth > 840:
            self.handle_authentication()
        
        return self.auth_headers


    def handle_instance_url(self):
        """
        prompts user for their plextrac url, checks that the API is up and running, then sets the url
        """
        if not self.base_url:
            self.base_url = input.prompt_user("Please enter the full URL of your PlexTrac instance (with protocol)", 
                                            "Instance URL is required but not provided")
        else:
            log.info(f'Using instance_url from config...')

        try:
            response = api.tenant.root_request(self.base_url, {})
            log.debug(response)
            if not response.has_json_response:
                if input.retry("Could not validate URL. Either the API is offline or it was entered incorrectly\nExample: https://company.plextrac.com", 
                             "Could not validate URL. Either the API is offline or it was entered incorrectly"):
                    self.base_url = None
                    return self.handle_instance_url()
                return

            if response.json.get('text') == "Authenticate at /authenticate":
                log.success("Validated instance URL")
                return

            if input.retry("Could not validate instance URL.", "Could not validate instance URL"):
                self.base_url = None
                return self.handle_instance_url()

        except Exception as e:
            log.exception(e)
            if input.retry("Could not validate URL. Either the API is offline or it was entered incorrectly\nExample: https://company.plextrac.com", 
                         "Could not validate URL. Either the API is offline or it was entered incorrectly"):
                self.base_url = None
                return self.handle_instance_url()


    def handle_authentication(self):
        log.info('---Starting Authorization---')

        self.handle_instance_url()

        if not self.username:
            self.username = input.prompt_user("Please enter your PlexTrac username", 
                                            "Username is required but not provided")
        else:
            log.info(f'Using username from config...')
        if not self.password:
            self.password = input.prompt_password("Password", "Password is required but not provided")
        else:
            log.info(f'Using password from config...')
        
        authenticate_data = {
            "username": self.username,
            "password": self.password
        }
        
        response = api._authentication.authenticate.authentication(self.base_url, self.auth_headers, authenticate_data)
        
        # the following conditional can fail due to:
        # - invalid credentials
        # - if the instance is setup to requre mfa and use user does not have mfa setup
        # - other
        # the api response is purposely non-descript to prevent gaining information about the authentication process
        if response.json.get('status') != "success":
            if input.retry("Could not authenticate with entered credentials.", "Could not authenticate with provided credentials"):
                self.username = None
                self.password = None
                self.tenant_id = None
                return self.handle_authentication()
        
        self.tenant_id = response.json.get('tenant_id')

        if response.json.get('mfa_enabled'):
            log.info('MFA detected for user')

            mfa_auth_data = {
                "code": response.json.get('code'),
                "token": input.prompt_user("Please enter your 6 digit MFA code", "MFA is enabled but interactive mode is disabled. Cannot prompt for MFA code")
            }
            
            response = api._authentication.authenticate.multi_factor_authentication(self.base_url, self.auth_headers, mfa_auth_data)
            if response.json.get('status') != "success":
                if input.retry("Invalid MFA Code.", "Invalid MFA Code"):
                    return self.handle_authentication()

        self.add_auth_header(response.json.get('token'))
        self.time_since_last_auth = time.time()
        log.success('Authenticated')
