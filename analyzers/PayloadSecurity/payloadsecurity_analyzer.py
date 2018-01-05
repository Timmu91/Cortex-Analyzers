#!/usr/bin/env python
# encoding: utf-8

from cortexutils.analyzer import Analyzer
import requests
from requests.auth import HTTPBasicAuth
import time


class PayloadSecurityAnalyzer(Analyzer):
    def __init__(self):
        Analyzer.__init__(self)
        self.service = self.getParam('config.service', None, 'PayloadSecurity service is missing')
        self.url = self.getParam('config.url', None, 'PayloadSecurity url is missing')
        self.apikey = self.getParam('config.key', None, 'PayloadSecurity apikey is missing')
        self.secret = self.getParam('config.secret', None, 'PayloadSecurity secret is missing')
        self.environmentid = self.getParam('config.environmentid', None, 'PayloadSecurity environmentid is missing')
        self.timeout = self.getParam('config.timeout', 15, None)
        self.verify = self.getParam('config.verifyssl', True, None)
        if not self.verify:
            from requests.packages.urllib3.exceptions import InsecureRequestWarning
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    def summary(self, raw):
        taxonomies = []
        level = "safe"
        namespace = "PayloadSecurity"
        predicate = "ThreatScore"
        value = "\"0/100\""

        result = {
            'service': self.service,
            'dataType': self.data_type
        }
        result["verdict"] = raw.get("verdict", None)
        result["vxfamily"] = raw.get("vxfamily", None)
        result["threatscore"] = raw.get("threatscore", None)

        if result["verdict"] == "malicious":
            level = "malicious"
        elif result["verdict"] == "suspicious":
            level = "suspicious"
        else:
            level = "safe"

        if result.get("threatscore"):
            value = "\"{}/100\"".format(result["threatscore"])

        taxonomies.append(self.build_taxonomy(level, namespace, predicate, value))

        return {"taxonomies": taxonomies}

    def run(self):
        Analyzer.run(self)

        try:

            user_agent = {'User-agent': 'Cortex Analyzer'}

            # Submit Analysis
            # File
            if self.service in ['file_analysis']:
                data = {'environmentId': self.environmentid, 'comment': 'Submitted by Cortex'}
                filepath = self.getParam('file', None, 'File is missing')
                f = open(filepath, "rb")
                files = {"file": f}
                response = requests.post(self.url.strip('/') + '/api/submit', data=data, headers=user_agent,
                                         files=files, auth=HTTPBasicAuth(self.apikey, self.secret), verify=self.verify)
                if response.status_code == 200:
                    data = response.json()
                    if data['response_code'] == 0:
                        if data.get('response'):
                            if data['response'].get('sha256'):
                                sha256 = data['response']['sha256']
                    elif data['response_code'] != 0:
                        if data.get('response'):
                            if data['response'].get('error'):
                                self.error(data['response']['error'])
                        else:
                            self.error('unknown error return by server')
                    else:
                        self.error('unknown error return by server')
                elif response.status_code == 400:
                    self.error('File upload failed or unknown submission related error')
                elif response.status_code == 429:
                    self.error('Your API key quota has been reached')
                else:
                    self.error('Unknown Server Error')

            # URL
            elif self.service == 'url_analysis':
                data = {'environmentId': self.environmentid, 'analyzeurl': self.getData(),
                        'comment': 'Submitted by Cortex'}
                response = requests.post(self.url.strip('/') + '/api/submiturl', data=data, headers=user_agent,
                                         verify=self.verify, auth=HTTPBasicAuth(self.apikey, self.secret))
                if response.status_code == 200:
                    data = response.json()
                    if data['response_code'] == 0:
                        if data.get('response'):
                            if data['response'].get('sha256'):
                                sha256 = data['response']['sha256']
                    elif data['response_code'] != 0:
                        if data.get('response'):
                            if data['response'].get('error'):
                                self.error(data['response']['error'])
                        else:
                            self.error('unknown error return by server')
                    else:
                        self.error('Not expected answer received from server')
                elif response.status_code == 400:
                    self.error('File upload failed or unknown submission related error')
                elif response.status_code == 429:
                    self.error('Your API key quota has been reached')
                else:
                    self.error('Unknown Server Error')

            else:
                self.error('Unknown PayloadSecurity service error')

            # Check analysis status
            stateUrl = self.url.strip('/') + '/api/state/' + sha256
            params = {'environmentId': self.environmentid}
            finished = False
            tries = 0
            while not finished and tries <= self.timeout:
                time.sleep(60)
                response = requests.get(stateUrl, headers=user_agent, params=params, verify=self.verify,
                                        auth=HTTPBasicAuth(self.apikey, self.secret))
                data = response.json()
                if data["response_code"] == 0 and data["response"]["state"] == 'SUCCESS':
                    finished = True
                tries += 1
            if not finished:
                self.error('PayloadSecurity analysis timed out')

            # Retrieve report summary
            report = {}
            summaryUrl = self.url.strip('/') + '/api/summary/' + sha256
            params = {'environmentId': self.environmentid, 'type': 'json'}
            response = requests.get(summaryUrl, headers=user_agent, params=params, verify=self.verify,
                                    auth=HTTPBasicAuth(self.apikey, self.secret))
            if response.status_code == 200:
                data = response.json()
                if data['response_code'] == 0 and data.get('response'):
                    report = data['response']
                    report['reporturl'] = self.url.strip('/') + '/sample/' + sha256 + '?environmentId=' + str(
                        self.environmentid)
                else:
                    self.error('unknown error return by server')
            else:
                self.error('Unknown Server Error')

            # Retrieve associated screenshots
            # Associated Sha256 can be different if submitted file is an archive
            if 'sha256' in report:
                sha256 = report['sha256']
            screenshotsUrl = self.url.strip('/') + '/api/sample-screenshots/' + sha256
            params = {'environmentId': self.environmentid, 'type': 'json'}
            response = requests.get(screenshotsUrl, headers=user_agent, params=params, verify=self.verify,
                                    auth=HTTPBasicAuth(self.apikey, self.secret))
            if response.status_code == 200:
                data = response.json()
                if data['response_code'] == 0 and data.get('response') and data['response'].get('screenshots'):
                    report['screenshots'] = data['response']['screenshots']
                else:
                    self.error('unknown error return by server')
            else:
                self.error('Unknown Server Error')

            if 'reporturl' in report:
                self.report(report)

        except requests.exceptions.RequestException as e:
            self.error(e)

        except Exception as e:
            self.unexpectedError(e)


if __name__ == '__main__':
    PayloadSecurityAnalyzer().run()
