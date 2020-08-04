# -*- coding: utf-8 -*-

import os
import re
from addict import Dict
from marshmallow import Schema, fields, validates_schema, ValidationError, post_load
from humanfriendly import parse_size, InvalidSize


_name_regex = re.compile(r'[a-z]([-a-z0-9]*[a-z0-9])?$')

class IntOrStrField(fields.Field):
    def _deserialize(self, value, attr, data, **kwargs):
        if isinstance(value, str) or isinstance(value, int):
            return value
        else:
            raise ValidationError('Field should be str or integer')


class StrictSchema(Schema):
    @validates_schema(pass_original=True)
    def check_unknown_fields(self, data, original_data):
        if original_data is None:
            raise ValidationError("the data passed the schema is null")
        unknown = set(original_data) - set(self.fields) - set(field.load_from for field in self.fields.values())
        if unknown:
            raise ValidationError('Unknown fields: {}, please check the docs'.format(unknown))

    class Meta:
        strict = True
        ordered = True


def validate_appname(name):
    if _name_regex.match(name) is None:
        raise ValidationError("appname is invalid")


def validate_jobname(name):
    if _name_regex.match(name) is None:
        raise ValidationError("jobname is invalid")


def validate_app_type(ss):
    if ss not in ("web", "worker"):
        raise ValidationError("app type should be `web`, `worker`")


def validate_spark_apptype(ss):
    if ss not in ("sparkapplication", "scheduledsparkapplication"):
        raise ValidationError("spark apptype should be `sparkapplication`, `scheduledsparkapplication`")


def validate_spark_type(ss):
    if ss not in ("Python", "Scala"):
        raise ValidationError("spark type should be `Python`, `Scala`")


def validate_spark_mode(mode):
    if mode not in ("client", "cluster"):
        raise ValidationError("spark mode should be `client`, `cluster`")


def validate_schedule(ss):
    #TODO
    pass


def validate_tag(tag):
    regex = re.compile(r'[\w][\w.-]{0,127}$')
    if regex.match(tag) is None:
        raise ValidationError("tag is invalid")


def validate_port(n):
    if not 0 < n <= 65535:
        raise ValidationError('Port must be 0-65,535')


def validate_protocol(ss):
    if ss not in ("TCP", "UDP"):
        raise ValidationError("protocol should be TCPor UDP")


def validate_env_list(l):
    for env in l:
        if len(env.split("=")) != 2:
            raise ValidationError("environment should conform to format: key=val")


def validate_image_pull_policy(ss):
    if ss not in ('Always', 'Never', 'IfNotPresent'):
        raise ValidationError("invalid imagePullPolicy value, only one of Always, Never, IfNotPresent is allowed")


def validate_abs_path(ss):
    if not os.path.isabs(ss):
        raise ValidationError("{} is not an absolute path".format(ss))


def validate_abs_path_list(lst):
    for l in lst:
        if l[0] != '/':
            raise ValidationError("{} is not a absolute path".format(l))


def validate_mountpoints(lst):
    hosts = set()
    for mp in lst:
        host = mp['host']
        if host in hosts:
            raise ValidationError('{} duplicate domain.'.format(host))
        hosts.add(host)


def validate_pod_volumes(lst):
    for vol in lst:
        if 'name' not in vol:
            raise ValidationError("need `name` field for volume")
        if 'persistentVolumeClaim' in vol:
            pvc = vol['persistentVolumeClaim']
            if not isinstance(pvc, dict):
                raise ValidationError("wrong PVC volume")
            if 'claimName' not in pvc:
                raise ValidationError("need `claimName` field for PVC volume")
        # notify use to use built-in Secret support
        if 'secret' in vol:
            raise ValidationError("please don't use Secret directly")
        # notify user to use built-in ConfigMap support
        if 'configMap' in vol:
            raise ValidationError("please don't use ConfigMap directly")
        if 'hostPath' in vol:
            host_path = vol['hostPath']
            if not isinstance(host_path, dict):
                raise ValidationError('wrong format for `hostPath` volumes')
            if 'path' not in host_path:
                raise ValidationError('need `path` field for hostPath volumes')
            inner_path = host_path['path']
            # 杜绝安全问题，避免瞎搞，比如将整个根目录挂载到容器(其实应该做的更严格，比如每个app一个目录)
            if not inner_path.startswith('/data/kae'):
                raise ValidationError('hostPath volume\'s path must be subdirectory of /data/kae')


def validate_build_name(name):
    if ':' in name:
        raise ValidationError("build name can't contain `:`.")


def validate_update_strategy_type(ss):
    if ss not in ("RollingUpdate", "Recreate"):
        raise ValidationError("strategy type must be RollingUpdate or Recreate")


def validate_percentage_or_int(ss):
    if ss.endswith('%'):
        ss = ss[:-1]
    try:
        if int(ss) < 0:
            raise ValidationError("must be positive number or zero.")
    except ValueError:
        raise ValidationError("invalid percentage or integer")


def validate_str_dict(dd):
    for k, v in dd.items():
        if not isinstance(k, str):
            raise ValidationError("key should be a string")
        if not isinstance(v, str):
            raise ValidationError("value should be a string")


def validate_cpu(d):
    for k, v in d.items():
        if k not in ('request', "limit"):
            raise ValidationError("cpu dict's key should be request or limit")
        try:
            if v[-1] == 'm':
                v = v[:-1]
            if float(v) < 0:
                raise ValidationError('CPU must >=0')
        except:
            raise ValidationError("invalid cpu value format")


def validate_memory(d):
    for k, v in d.items():
        if k not in ('request', "limit"):
            raise ValidationError("memory dict's key should be request or limit")
        try:
            if parse_size(v) <= 0:
                raise ValidationError("memory should bigger than zero")
        except InvalidSize:
            raise ValidationError("invalid memory value format")


def validate_docker_volumes(lst):
    for l in lst:
        if ':' not in l:
            raise ValidationError('wrong docker volumes')
        parts = l.split(':', 1)
        if (not os.path.isabs(parts[0])) or (not os.path.isabs(parts[1])):
            raise ValidationError('host path and container path must be absolute path')


class Mountpoint(StrictSchema):
    host = fields.Str(required=True)
    path = fields.Str(missing="/")
    paths = fields.List(fields.Str(), missing=['/'])
    tlsSecret = fields.Str()


class ContainerPort(StrictSchema):
    containerPort = fields.Int(validate=validate_port)
    hostIP = fields.Str()
    hostPort = fields.Int(validate=validate_port)
    name = fields.Str()
    protocol = fields.Str(validate=validate_protocol)


class BuildSchema(StrictSchema):
    name = fields.Str(validate=validate_build_name)
    tag = fields.Str(validate=validate_tag)
    dockerfile = fields.Str()
    target = fields.Str()
    args = fields.Dict()


class RollingUpdate(StrictSchema):
    maxSurge = fields.Str(missing="25%", validate=validate_percentage_or_int)
    maxUnavailable = fields.Str(missing="25%", validate=validate_percentage_or_int)


class UpdateStrategy(StrictSchema):
    type = fields.Str(missing="RollingUpdate", validate=validate_update_strategy_type)
    # only valid when type is RollingUpdate
    rollingUpdate = fields.Nested(RollingUpdate)


class ConfigMapSchema(StrictSchema):
    dir = fields.Str(required=True)
    key = fields.Str(required=True)
    filename = fields.Str()

    @post_load
    def add_defaults(self, data):
        if 'filename' not in data:
            data['filename'] = data['key']
        if not os.path.isabs(data['dir']):
            raise ValidationError("{} is not a absolute path".format(data['dir']))
        return data


class SecretSchema(StrictSchema):
    envNameList = fields.List(fields.Str(), required=True)
    keyList = fields.List(fields.Str())

    @post_load
    def add_defaults(self, data):
        if 'keyList' not in data:
            data['keyList'] = data['envNameList']
        if len(data['keyList']) != len(data['envNameList']):
            raise ValidationError("the length of envNameList must equal to keyList")
        return data


class VolumeMountSchema(StrictSchema):
    name = fields.Str(required=True)
    mountPath = fields.Str(required=True)
    readOnly = fields.Bool(missing=False)
    subPath = fields.Str(missing="")


build_schema = BuildSchema()


class ContainerSpec(StrictSchema):
    name = fields.Str()
    image = fields.Str()
    imagePullPolicy = fields.Str(validate=validate_image_pull_policy)
    args = fields.List(fields.Str())
    command = fields.List(fields.Str())
    env = fields.List(fields.Str(), validate=validate_env_list)
    tty = fields.Bool()
    workingDir = fields.Str(validate=validate_abs_path)
    livenessProbe = fields.Dict()
    readinessProbe = fields.Dict()
    ports = fields.List(fields.Nested(ContainerPort))

    cpu = fields.Dict(validate=validate_cpu)
    memory = fields.Dict(validate=validate_memory)
    gpu = fields.Int()

    configs = fields.List(fields.Nested(ConfigMapSchema), missing=[])
    secrets = fields.Nested(SecretSchema)
    volumeMounts = fields.List(fields.Nested(VolumeMountSchema), missing=[])
    useDFS = fields.Bool(missing=False)

    @post_load
    def add_defaults(self, data):
        if "cpu" not in data:
            cpu = {"request": "100m", "limit": "200m"}
            data['cpu'] = cpu
        if "memory" not in data:
            memory = {"request": "64Mi", "limit": "128Mi"}
            data["memory"] = memory
        return data


class ServicePort(StrictSchema):
    name = fields.Str()
    port = fields.Int(required=True, validate=validate_port)
    targetPort = IntOrStrField()
    protocol = fields.Str(validate=validate_protocol, missing="TCP")


class HostAliases(StrictSchema):
    ip = fields.Str(required=True)
    hostnames = fields.List(fields.Str(), required=True)


class HPAMetric(StrictSchema):
    name = fields.Str(required=True)
    averageUtilization = fields.Int()
    averageValue = fields.Str()
    value = fields.Str()

    @validates_schema(pass_original=True)
    def further_check(self, data, original_data):
        name = data.get("name")
        if name.lower() not in ("cpu", "memory"):
            raise ValidationError("name msut be cpu or mempry")
        averageUtilization = data.get("averageUtilization")
        averageValue = data.get("averageValue")
        value = data.get("value")

        none_field_cnt = [averageUtilization, averageValue, value].count(None)
        if none_field_cnt != 2:
            raise ValidationError('you must specify one and only one field of averageUtilization, averageValue and value')


class HPA(StrictSchema):
    minReplicas = fields.Int(missing=1)
    maxReplicas = fields.Int(required=True)
    metrics = fields.List(fields.Nested(HPAMetric))

    @validates_schema(pass_original=True)
    def further_check(self, data, original_data):
        minReplicas = data.get("minReplicas")
        maxReplicas = data.get("maxReplicas")
        if maxReplicas < minReplicas:
            raise ValidationError("maxReplicas must not be less than minReplicas")
        metrics = data.get("metrics")
        if metrics is None or len(metrics) == 0:
            raise ValidationError("at least one metric is needed for HPA")


class ServiceSchema(StrictSchema):
    user = fields.Str(missing="root")
    registry = fields.Str()
    labels = fields.List(fields.Str())
    ingressAnnotations = fields.Dict(validate=validate_str_dict)
    httpsOnly = fields.Bool(missing=True)
    mountpoints = fields.List(fields.Nested(Mountpoint), validate=validate_mountpoints, missing=[])
    ports = fields.List(fields.Nested(ServicePort), required=True)

    replicas = fields.Int(missing=1)
    minReadySeconds = fields.Int()
    progressDeadlineSeconds = fields.Int()
    strategy = fields.Nested(UpdateStrategy)
    hostAliases = fields.List(fields.Nested(HostAliases))

    containers = fields.List(fields.Nested(ContainerSpec), required=True)
    volumes = fields.List(fields.Dict(), validate=validate_pod_volumes, missing=[])
    hpa = fields.Nested(HPA)
    @post_load
    def finalize(self, data):
        """add defaults to fields, and then construct a Dict"""
        # validate service port
        container_ports = [p for cont in data["containers"] for p in cont.get("ports", []) ]
        port_int_list, port_str_list = [], []
        for p in container_ports:
            if p.get("name") is not None:
                port_str_list.append(p.get('name'))
            port_int_list.append(p['containerPort'])

        svc_ports = data.get("ports", [])
        for p in svc_ports:
            targetPort = p.get("targetPort")
            if targetPort is None:
                continue
            if isinstance(targetPort, str):
                if targetPort not in port_str_list:
                    raise ValidationError("service targetPort doesn't stay in Container port list")
            elif isinstance(targetPort, int):
                if targetPort not in port_int_list:
                    raise ValidationError("service targetPort doesn't stay in Container port list")
        return Dict(data)


service_schema = ServiceSchema()


class TestEntrypointSchema(StrictSchema):
    image = fields.Str()
    volumes = fields.List(fields.Str(), validate=validate_docker_volumes)
    script = fields.List(fields.Str(), required=True)


class TestSchema(StrictSchema):
    builds = fields.List(fields.Nested(BuildSchema), missing=[])
    entrypoints = fields.List(fields.Nested(TestEntrypointSchema))


class AppSpecsSchema(StrictSchema):
    appname = fields.Str(required=True, validate=validate_appname)
    type = fields.Str(missing="worker", validate=validate_app_type)
    builds = fields.List(fields.Nested(BuildSchema), missing=[])
    service = fields.Nested(ServiceSchema, required=True)
    test = fields.Nested(TestSchema)

    @post_load
    def finalize(self, data):
        """add defaults to fields, and then construct a Dict"""
        build_names = set()
        for build in data["builds"]:
            name = build.get("name", None)
            if name:
                if name in build_names:
                    raise ValidationError("duplicate build name")
                build_names.add(name)

        if data["type"] == "web":
            ports = data["service"]["ports"]
            if len(ports) != 1:
                ValidationError("web service should contain only one port")
            for p in ports:
                if p["port"] != 80:
                    raise ValidationError("port of web service must be 80")
        return Dict(data)

    @validates_schema
    def validate_misc(self, data):
        # check raw related fields
        pass


app_specs_schema = AppSpecsSchema()


class JobSchema(StrictSchema):
    jobname = fields.Str(required=True, validate=validate_jobname)
    # the below 4 fields are not used by kubernetes
    git = fields.Str()
    branch = fields.Str(missing='master')
    commit = fields.Str()
    comment = fields.Str()

    backoffLimit = fields.Int()
    completions = fields.Int()

    parallelism = fields.Int()
    autoRestart = fields.Bool(missing=False)

    containers = fields.List(fields.Nested(ContainerSpec), required=True)

    @post_load
    def finalize(self, data):
        """add defaults to fields, and then construct a Box"""
        return Dict(data)


job_schema = JobSchema()


def load_job_specs(raw_data):
    """
    add defaults to fields, and then construct a Dict
    :param raw_data:
    :param tag: release tag
    :return:
    """
    data = job_schema.load(raw_data).data
    return Dict(data)


class SparkAppDriverSchema(StrictSchema):
    cpu = fields.Int(missing=1)
    memory = fields.Str(missing='512m')


class SparkAppExecutorSchema(StrictSchema):
    cpu = fields.Int(missing=1)
    memory = fields.Str(missing='512m')
    instances = fields.Int(missing=1)


class DependencesSchema(StrictSchema):
    jars = fields.List(fields.Str())
    files = fields.List(fields.Str())
    pyFiles = fields.List(fields.Str())


class SparkAppSchema(StrictSchema):
    apptype = fields.Str(required=True, validate=validate_spark_apptype)
    appname = fields.Str(required=True)
    role = fields.Str()
    schedule = fields.Str(validate=validate_schedule)
    concurrencyPolicy = fields.Str(missing='Allow')
    type = fields.Str(validate=validate_spark_type, missing='Python')
    image = fields.Str(required=True)
    imagePullPolicy = fields.Str(missing='Always')
    sparkVersion = fields.Str(missing='2.4.0')
    arguments = fields.List(fields.Str())
    nodeSelector = fields.Dict()
    pythonVersion = fields.Str(missing='3')
    driver = fields.Nested(SparkAppDriverSchema)
    executor = fields.Nested(SparkAppExecutorSchema)
    mainApplicationFile = fields.Str(required=True)
    deps = fields.Nested(DependencesSchema)
    mode = fields.Str(missing='cluster', validate=validate_spark_mode)
    hadoopConfigMap = fields.Str()
    serviceAccount = fields.Str()
    sparkConfigMap = fields.Str()
    comment = fields.Str()
    sparkConf = fields.Dict()
    hadoopConf = fields.Dict()

    @post_load
    def finalize(self, data):
        if data["apptype"] == "scheduledsparkapplication":
            if "schedule" not in data.keys():
                raise ValidationError("scheduledspark app must have `schedule` field")
        return Dict(data)


sparkapp_schema = SparkAppSchema()


def load_sparkapp_specs(raw_data):
    data = sparkapp_schema.load(raw_data).data
    return Dict(data)
