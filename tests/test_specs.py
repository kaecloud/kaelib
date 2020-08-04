# -*- coding: utf-8 -*-

import copy
import pytest
from marshmallow import ValidationError
import yaml
from kaelib.spec import (
    validate_appname, validate_tag, validate_docker_volumes,
    UpdateStrategy, ConfigMapSchema, SecretSchema, HPA, 
    AppSpecsSchema,
)


test_tmpl = """
appname: hello
type: web

builds:
- name: hello

service:
  user: root
  replicas: 2
  labels:
    - proctype=router

  mountpoints:
    - host: hello.geetest.com
      path: /
  ports:
  - port: 80
    targetPort: 8080

  containers:
  - name: hello-world
    # image: registry.cn-hangzhou.aliyuncs.com/kae/hello:0.1.1
    imagePullPolicy: Always
    # args: ["xx", "xx"]
    command: ['hello-world']

    env:                     # environments
      - ENVA=a
    tty: false               # whether allocate tty
    # workingDir: xxx          # working dir

    ports:
    - name: http-port
      containerPort: 8080
"""

def test_validate_appname():
    good_appnames = ['aaa', 'aaa-bbb', 'a1-bbb']
    bad_appnames = ['1a_aa', "aa_bb", "AAA", "aaa*bb", "aaa#bbb", "-"]
    for name in good_appnames:
        validate_appname(name)
    for name in bad_appnames:
        with pytest.raises(ValidationError):
            validate_appname(name)


def test_validate_tag():
    good_tags = ['aaa', "AAA", 'aaa-bbb', 'a1-bbb', "aa_bb", "_", "aa.bb"]
    bad_tags = ["aaa*bb", "aa#bbn"]
    for tag in good_tags:
        validate_tag(tag)
    for tag in bad_tags:
        with pytest.raises(ValidationError):
            validate_tag(tag)


def test_validate_docker_volumes():
    good_vals = [['/haha:/kakak'], ]
    bad_vals = [['hahah'], ['/hahah'], ['haha:/kkkk'], ['/hhah:bbbb']]
    for v in good_vals:
        validate_docker_volumes(v)
    for v in bad_vals:
        with pytest.raises(ValidationError):
            validate_docker_volumes(v)



# def test_container_spec():
#     container_spec = ContainerSpec()
#     container_spec.load(yaml.load(default_container))
#     yaml_dict = yaml.load(default_specs_text)
#     yaml_dict['service']['containers'] = [yaml.load(default_container)]
#     spec = specs_schema.load(yaml_dict).data
#     api = KubernetesApi(use_kubeconfig=True)
#     d, s, i = api.create_resource_dict(spec)
#     pprint.pprint(d[0].to_dict())


def test_svc_ports():
    schema = AppSpecsSchema()
    initial_dic = yaml.safe_load(test_tmpl)
    dic = copy.deepcopy(initial_dic)
    data = schema.load(dic).data

    # targetPort is not equal to port in container
    dic = copy.deepcopy(initial_dic)
    dic['service']['ports'][0]['targetPort'] = 1234
    with pytest.raises(ValidationError):
        schema.load(dic)

    # targetPort is not a valid container port name
    dic = copy.deepcopy(initial_dic)
    dic['service']['ports'][0]['targetPort'] = 'pppp'
    with pytest.raises(ValidationError):
        schema.load(dic)

    dic = copy.deepcopy(initial_dic)
    dic['service']['ports'][0]['targetPort'] = 'http-port'
    data = schema.load(dic).data
    assert data['service']['ports'][0]['targetPort'] == 'http-port'
    
    # no service port 
    dic = copy.deepcopy(initial_dic)
    dic['service'].pop('ports')
    with pytest.raises(ValidationError):
        data = schema.load(dic).data

    # no container port
    dic = copy.deepcopy(initial_dic)
    dic['service']['containers'][0].pop("ports")
    with pytest.raises(ValidationError):
        data = schema.load(dic).data


def test_configmap():
    tmpl = """
dir: /dir1
key: key1
filename: name1
    """
    initial_dic = yaml.safe_load(tmpl)
    schema = ConfigMapSchema()

    dic = copy.deepcopy(initial_dic)
    data = schema.load(dic).data
    assert data['dir'] == '/dir1'

    # missing filename case
    dic = copy.deepcopy(initial_dic)
    dic.pop('filename')
    data = schema.load(dic).data
    assert data['dir'] == '/dir1'
    assert data['filename'] == data['key'] == 'key1'

    # missing field
    with pytest.raises(ValidationError):
        schema.load({'dir': '/ddd'})

    # dir is not a absolute path
    with pytest.raises(ValidationError):
        schema.load({'dir': 'ddd', "key": "key1"})


def test_secrets():
    tmpl = """
envNameList:
  - aa
  - bb
keyList:
  - key1
  - key2
    """
    initial_dic = yaml.safe_load(tmpl)
    schema = SecretSchema()

    dic = copy.deepcopy(initial_dic)
    data = schema.load(dic).data
    assert data['envNameList'] == ['aa', 'bb'] and data['keyList'] == ['key1', 'key2']

    dic = copy.deepcopy(initial_dic)
    dic.pop('keyList')
    data = schema.load(dic).data
    assert data['envNameList'] == data['keyList'] == ['aa', 'bb']

    with pytest.raises(ValidationError) as e:
        _ = schema.load({"envNameList": ["aa", "bb"], "keyList": []}).data


def test_update_strategy():
    tmpl = """
type: RollingUpdate
rollingUpdate:
  maxSurge: 25%
  maxUnavailable: 35%
    """
    dic = yaml.safe_load(tmpl)
    schema = UpdateStrategy()
    data = schema.load(dic).data
    assert data['rollingUpdate']['maxSurge'] == '25%'

    # maxSurge, maxUnavailable validate
    dic['rollingUpdate']['maxSurge'] = '2a5%'
    with pytest.raises(ValidationError) as e:
        _ = schema.load(dic).data
    dic['rollingUpdate']['maxSurge'] = '-25%'
    with pytest.raises(ValidationError) as e:
        _ = schema.load(dic).data

    # type validate
    with pytest.raises(ValidationError) as e:
        _ = schema.load({"type": "hahahn"}).data


def test_hpa():
    tmpl = """
minReplicas: 2
maxReplicas: 3
metrics:
  - name: cpu
    averageUtilization: 50
    """
    dic = yaml.safe_load(tmpl)
    schema = HPA()
    data = schema.load(dic).data
    assert data["maxReplicas"] == 3
    assert data["minReplicas"] == 2

    # maxReplicas
    new_dic = copy.deepcopy(dic)
    new_dic["maxReplicas"] = 1
    with pytest.raises(ValidationError) as e:
        _ = schema.load(new_dic).data

    new_dic = copy.deepcopy(dic)
    new_dic.pop("metrics")
    with pytest.raises(ValidationError) as e:
        _ = schema.load(new_dic).data

    new_dic = copy.deepcopy(dic)
    new_dic["metrics"][0]["name"] = "haha"
    with pytest.raises(ValidationError) as e:
        _ = schema.load(new_dic).data

    new_dic = copy.deepcopy(dic)
    new_dic["metrics"][0]["averageValue"] = "haha"
    with pytest.raises(ValidationError) as e:
        _ = schema.load(new_dic).data
