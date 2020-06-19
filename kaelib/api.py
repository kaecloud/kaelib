#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""

"""
from __future__ import print_function, division, absolute_import
import six
from six.moves.urllib.parse import urljoin
import re
import os
import pickle
import logging
import json as jsonlib
import requests
from requests.auth import HTTPBasicAuth

from requests import Session
import websocket

logger = logging.getLogger(__name__)


OPCODE_DATA = (websocket.ABNF.OPCODE_TEXT, websocket.ABNF.OPCODE_BINARY)


class KaeAPIError(Exception):
    def __init__(self, http_code, msg):
        self.http_code = http_code
        self.msg = msg

    def __str__(self):
        return self.msg


def recv(ws):
    try:
        frame = ws.recv_frame()
    except websocket.WebSocketException:
        return websocket.ABNF.OPCODE_CLOSE, None
    if not frame:
        raise websocket.WebSocketException("Not a valid frame %s" % frame)
    elif frame.opcode in OPCODE_DATA:
        return frame.opcode, frame.data
    elif frame.opcode == websocket.ABNF.OPCODE_CLOSE:
        ws.send_close()
        return frame.opcode, None
    elif frame.opcode == websocket.ABNF.OPCODE_PING:
        ws.pong(frame.data)
        return frame.opcode, frame.data

    return frame.opcode, frame.data


def recv_ws(ws):
    while True:
        opcode, data = recv(ws)
        msg = None
        if six.PY3 and opcode == websocket.ABNF.OPCODE_TEXT and isinstance(data, bytes):
            data = str(data, "utf-8")
        if opcode in OPCODE_DATA:
            msg = data

        if msg is not None:
            yield msg

        if opcode == websocket.ABNF.OPCODE_CLOSE:
            print('closed')
            break


class KaeAPI:
    def __init__(self, host, version='v1', timeout=None,
                 access_token=None, cluster='default'):
        self.host = host
        self.version = version
        self.timeout = timeout
        self.cluster = cluster

        self.host = host
        self.base = '%s/api/%s/' % (self.host, version)
        self.session = Session()

        if access_token:
            self.session.headers.update({
                'Authorization': 'Bearer {}'.format(access_token),
            })

    def set_access_token(self, access_token):
        self.session.headers.update({
            'Authorization': 'Bearer {}'.format(access_token),
        })

    def set_base_auth(self, user, password):
        auth = HTTPBasicAuth(user, password)
        auth(self.session)

    def set_real_user(self, real_user):
        self.session.headers.update({'X-Real-User': real_user})

    def set_cluster(self, cluster):
        self.cluster = cluster

    def request(self, path, method='GET', params=None, data=None, json=None, files=None, **kwargs):
        """Wrap around requests.request method"""
        url = urljoin(self.base, path)
        params = params or {}
        resp = self.session.request(url=url,
                                    method=method,
                                    params=params,
                                    data=data,
                                    json=json,
                                    timeout=self.timeout,
                                    files=files,
                                    **kwargs)
        code = resp.status_code
        if code != 200:
            raise KaeAPIError(code, resp.text)
        try:
            response = resp.json()
        except ValueError:
            # when console don't return json, it means a bug
            raise KaeAPIError(500, 'BUG: Console did not return json, body {}'.format(resp.text))
        return response

    def request_ws(self, path, params=None, data=None, json=None, ignore_decode_err=False):
        url = urljoin(self.base, path)
        url = re.sub(r'^http', 'ws', url)
        headers = {
            'Authorization': self.session.headers['Authorization'],
        }
        if 'X-Real-User' in self.session.headers:
            headers['X-Real-User'] = self.session.headers['X-Real-User']

        options = {
            'header': headers,
        }

        ws = websocket.create_connection(url, **options)
        ws.send(jsonlib.dumps(json))
        for msg in recv_ws(ws):
            try:
                data = jsonlib.loads(msg)
                yield data
            except jsonlib.JSONDecodeError:
                if ignore_decode_err:
                    # print("decode json error, ignore it")
                    continue
                else:
                    raise KaeAPIError(500, "json decode error {}".format(msg))
            except (ValueError, TypeError):
                raise KaeAPIError(500, msg)

    def list_app(self):
        return self.request('app/')

    def get_app(self, appname):
        return self.request('app/%s' % appname)

    def delete_app(self, appname):
        return self.request('app/%s' % appname, method='DELETE')

    def get_app_users(self, appname):
        return self.request('app/%s/users' % appname)

    def grant_user(self, appname, username=None, email=None):
        params = {}
        if username is not None:
            params['username'] = username
        elif email is not None:
            params['email'] = email
        else:
            raise ValueError("you need pass username or email")
        return self.request('app/%s/users' % appname, method='PUT', json=params)

    def revoke_user(self, appname, username=None, email=None):
        params = {}
        if username is not None:
            params['username'] = username
        elif email is not None:
            params['email'] = email
        else:
            raise ValueError("you need pass username or email")
        return self.request('app/%s/users' % appname, method='DELETE', json=params)

    def get_app_pods(self, appname, canary=False, watch=False):
        params = {
            'cluster': self.cluster,
            'canary': canary,
        }
        if watch is False:
            return self.request('app/%s/pods' % appname, params=params)
        else:
            return self.request_ws('ws/app/%s/pods/events' % appname, json=params)

    def watch_app_pods(self, appname, canary=False):
        payload = {
            'cluster': self.cluster,
            'canary': canary,
        }
        return self.request_ws('ws/app/%s/pods/events' % appname, json=payload)

    def get_app_releases(self, appname):
        return self.request('app/%s/releases' % appname)

    def get_app_deployment(self, appname, canary=False):
        params = {
            'cluster': self.cluster,
            'canary': canary,
        }
        return self.request('app/%s/deployment' % appname, params=params)

    def get_release(self, appname, tag):
        return self.request('app/%s/version/%s' % (appname, tag))

    def get_secret(self, appname):
        params = {
            'cluster': self.cluster,
        }
        return self.request('app/%s/secret' % appname, params=params)

    def set_secret(self, appname, data, replace=False):
        payload = {
            'cluster': self.cluster,
            'data': data,
            'replace': replace,
        }
        return self.request('app/%s/secret' % appname, method="POST", json=payload)

    def get_config(self, appname):
        params = {
            'cluster': self.cluster,
        }
        return self.request('app/%s/configmap' % appname, params=params)

    def set_config(self, appname, data, replace=False):
        payload = {
            'cluster': self.cluster,
            'data': data,
            'replace': replace,
        }
        return self.request('app/%s/configmap' % appname, method="POST", json=payload)

    def list_app_yaml(self, appname):
        return self.request('app/%s/yaml' % appname)

    def create_app_yaml(self, appname, name, specs_text, comment=None):
        params = {
            'name': name,
            'specs_text': specs_text,
        }
        if comment is not None:
            params['comment'] = comment
        return self.request('app/%s/yaml' % appname, method='POST', json=params)

    def update_app_yaml(self, appname, name, new_name, specs_text, comment=None):
        params = {
            'name': new_name,
            'specs_text': specs_text,
        }
        if comment is not None:
            params['comment'] = comment
        return self.request('app/%s/name/%s/yaml' % (appname, name), method='POST', json=params)

    def delete_app_yaml(self, appname, name):
        return self.request('app/%s/name/%s/yaml' % (appname, name), method='DELETE')

    def register_release(self, appname, tag, git, specs_text, branch=None, force=False):
        payload = {
            'appname': appname,
            'tag': tag,
            'git': git,
            'specs_text': specs_text,
            'branch': branch,
            'force': force,
        }
        return self.request('app/register', method='POST', json=payload)

    def rollback(self, appname, revision=0, deploy_id=None):
        payload = {
            'cluster': self.cluster,
            'revision': revision,
        }
        if deploy_id is not None:
            payload['deploy_id'] = deploy_id
        return self.request('app/%s/rollback' % appname, method='PUT', json=payload)

    def renew(self, appname):
        payload = {
            'cluster': self.cluster,
        }
        return self.request('app/%s/renew' % appname, method='PUT', json=payload)

    def build_app(self, appname, tag, block=False, ignore_decode_err=True):
        payload = {
            'tag': tag,
            'block': block,
        }
        return self.request_ws('ws/app/%s/build' % appname, json=payload,
                               ignore_decode_err=ignore_decode_err)

    def deploy_app(self, appname, tag, cpus=None, memories=None, replicas=None, app_yaml_name=None, use_newest_config=False):
        """deploy app.
        appname:
        tag: 要部署的版本号, git tag的值.
        cpus: 需要的cpu个数, 例如1, 或者1.5, 如果是public的部署, 传0.
        memories: 最小4MB.
        replicas: app的副本数量
        app_yaml_name: AppYaml template name
        """
        payload = {
            'cluster': self.cluster,
            'tag': tag,
            'cpus': cpus,
            'memories': memories,
            'replicas': replicas,
            'app_yaml_name': app_yaml_name,
            'use_newest_config': use_newest_config,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        return self.request('app/%s/deploy' % appname, method='PUT', json=payload)

    def undeploy_app(self, appname, cluster=None):
        """undeploy app.
        appname: App name
        """
        if cluster is None:
            cluster = self.cluster
        payload = {
            'cluster': cluster,
        }
        return self.request('app/%s/undeploy' % appname, method='DELETE', json=payload)

    def deploy_app_canary(self, appname, tag, cpus=None, memories=None, replicas=None, app_yaml_name=None, use_newest_config=False):
        """deploy canary version of specified app
        appname:
        tag: 要部署的版本号, git tag的值.
        cpus: 需要的cpu个数, 例如1, 或者1.5, 如果是public的部署, 传0.
        memories: 最小4MB.
        replicas: app的副本数量
        app_yaml_name: AppYaml template name
        """
        payload = {
            'cluster': self.cluster,
            'tag': tag,
            'cpus': cpus,
            'memories': memories,
            'replicas': replicas,
            'app_yaml_name': app_yaml_name,
            'use_newest_config': use_newest_config,
        }

        payload = {k: v for k, v in payload.items() if v is not None}
        return self.request('app/%s/canary/deploy' % appname, method='PUT', json=payload)

    def undeploy_app_canary(self, appname, cluster=None):
        """undeploy canary version of specified app
        appname:
        """
        if cluster is None:
            cluster = self.cluster
        payload = {
            'cluster': cluster,
        }

        payload = {k: v for k, v in payload.items() if v is not None}
        return self.request('app/%s/canary/undeploy' % appname, method='DELETE', json=payload)

    def delete_app_canary(self, appname):
        payload = {
            'cluster': self.cluster,
        }
        return self.request('app/%s/canary' % appname, method='DELETE', json=payload)

    def scale_app(self, appname, replicas):
        """deploy app.
        replicas: app的副本数量
        """
        payload = {
            'cluster': self.cluster,
            'replicas': replicas,
        }

        return self.request('app/%s/scale' % appname, method='PUT', json=payload)

    def set_app_abtesting_rules(self, appname, rules):
        """deploy app.
        cpu: 需要的cpu个数, 例如1, 或者1.5, 如果是public的部署, 传0.
        memory: 最小4MB.
        replicas: app的副本数量
        """
        payload = {
            'cluster': self.cluster,
            'rules': rules,
        }
        return self.request('app/%s/abtesting' % appname, method='PUT', json=payload)

    def stop_container(self, appname, podname, container, namespace, cluster=None):
        if cluster is None:
            cluster = self.cluster
        payload = {
            'cluster': cluster,
            'podname': podname,
            'container': container,
            'namespace': namespace,
        }
        return self.request('app/%s/container/stop' % appname, method='POST', json=payload)

    def kill_build_task(self, appname):
        return self.request('app/%s/build/kill' % appname, method='DELETE')

    def create_job(self, specs_text=None, **kwargs):
        payload = kwargs
        if specs_text:
            payload = {
                'specs_text': specs_text,
            }
        return self.request('job', method='POST', json=payload)

    def list_job(self):
        return self.request('job', method='GET')

    def delete_job(self, jobname):
        return self.request('job/%s' % jobname, method='DELETE')

    def get_job_log(self, jobname, follow=False):
        if follow is False:
            return self.request('job/%s/log' % jobname)
        else:
            return self.request_ws('ws/job/%s/log/events' % jobname)

    def create_sparkapp(self, data=None, spec_text=None):
        payload = data
        if spec_text:
            payload = {
                'spec_text': spec_text,
            }
        return self.request('spark', method='POST', json=payload)

    def list_sparkapp(self):
        return self.request('spark', method='GET')

    def delete_sparkapp(self, appname):
        return self.request('spark/%s' % appname, method='DELETE')

    def restart_sparkapp(self, appname):
        return self.request('spark/%s/restart' % appname, method='PUT')

    def get_sparkapp_log(self, appname, follow=False):
        if follow is False:
            return self.request('spark/%s/log' % appname)
        else:
            return self.request_ws('ws/spark/%s/log/events' % appname)

    def upload(self, appname, filetype, files):
        data = {
            'fileType': filetype
        }

        return self.request('spark/%s/upload' % appname, data=data, files=files, method='POST')
