#!/usr/bin/env pyhton3
# -*- coding:utf-8 -*-

from CTFd.utils.decorators import admins_only
from CTFd.utils.user import is_admin
from CTFd.cache import cache
from CTFd.models import db
from .models import Containers

import json
import subprocess
import socket
import tempfile
import re
import sys
import random


@cache.memoize()
def can_create_container():
    try:
        subprocess.check_output(['docker', 'version'])
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def container_status(container_id):
    print('runing ' + sys._getframe().f_code.co_name + ' function')
    try:
        cmd = ['docker', 'inspect', '--type=container', str(container_id)]
        # print(cmd)
        info = json.loads(subprocess.check_output(
            cmd))
        # print(info)
        status = info[0]["State"]["Status"]
        portbinds = info[0]["HostConfig"]["PortBindings"]
        publish_port = ''
        for expose_port in portbinds.keys():
            host_port = portbinds[expose_port][0]["HostPort"]
            publish_port += '{}-->{} '.format(host_port, expose_port)

        return status, publish_port
    except subprocess.CalledProcessError:
        return 'missing', ''


def container_ports(name, verbose=False):
    print('runing ' + sys._getframe().f_code.co_name + ' function')
    try:
        if not name:
            return []
        info = json.loads(subprocess.check_output(
            ['docker', 'inspect', '--type=container', name]))
        if verbose:
            ports = info[0]["NetworkSettings"]["Ports"]
            if not ports:
                return []
            final = []
            for port in ports.keys():
                final.append("".join([ports[port][0]["HostPort"], '->', port]))
            return final
        else:
            ports = info[0]['Config']['ExposedPorts'].keys()
            if not ports:
                return []
            ports = [int(re.sub('[A-Za-z/]+', '', port)) for port in ports]
            return ports
    except subprocess.CalledProcessError:
        return []


def is_port_free(port):
    port = int(port)
    print('runing ' + sys._getframe().f_code.co_name + ' function')
    s = socket.socket()
    result = s.connect_ex(('127.0.0.1', port))
    if result == 0:
        s.close()
        return False
    return True


def import_image(name, ports):
    try:
        info = json.loads(subprocess.check_output(
            ['docker', 'inspect', '--type=image', name]))
        image_id = str(info[0]['Id'].split(':')[1][0:6])
        image_name = str(info[0]['RepoTags'][0])

        # 判断是否存在容器
        containers = Containers.query.filter_by(
            name=image_name).first()
        if not containers == None:
            return False
        cmd = ['docker', 'ps', '-a', '--filter', 'ancestor=' + name,
               '--format', '\"{{.ID}}\"']
        container_id = subprocess.check_output(cmd).decode()

        if container_id == '':
            container_id = None
        else:
            # b'"d6c77280b94a"\n"6006a7aa486c"\n'
            container_id = eval(container_id.split('\n')[0])

        container = Containers(name=image_name, image_id=image_id,
                               container_id=container_id, ports=ports, buildfile=None)
        db.session.add(container)
        db.session.commit()
        db.session.close()
        return True
    except subprocess.CalledProcessError:
        return False


def image_import_all():
    try:
        # 获取所有image的id
        image_ids = subprocess.check_output(
            ['docker', 'images', '-q']).decode('utf-8')
        image_ids = image_ids.split('\n')[0:-1]

        for image_id in image_ids:
            import_image(image_id, ports='')

        return True
    except subprocess.CalledProcessError:
        return False


def image_create(name, buildfile, files):
    print('runing ' + sys._getframe().f_code.co_name + ' function')
    if not can_create_container():
        return False
    folder = tempfile.mkdtemp(prefix='ctfd')
    tmpfile = tempfile.NamedTemporaryFile(dir=folder, delete=False)
    tmpfile.write(buildfile)
    tmpfile.close()

    for f in files:
        if f.filename.strip():
            filename = os.path.basename(f.filename)
            f.save(os.path.join(folder, filename))
    # repository name component must match "[a-z0-9](?:-*[a-z0-9])*(?:[._][a-z0-9](?:-*[a-z0-9])*)*"
    # docker build -f tmpfile.name -t name
    try:
        cmd = ['docker', 'build', '-f', tmpfile.name, '-t', name, folder]
        print(cmd)
        subprocess.call(cmd)
        container = Containers(
            name=name, buildfile=buildfile, image_id=None, container_id=None,)
        db.session.add(container)
        db.session.commit()
        db.session.close()
        rmdir(folder)
        return True
    except subprocess.CalledProcessError:
        return False


def image_run(name, ports):
    print('runing ' + sys._getframe().f_code.co_name + ' function')
    try:
        info = json.loads(subprocess.check_output(
            ['docker', 'inspect', '--type=image', name]))

        cmd = ['docker', 'run', '-d']
        ports_asked = ports.split(',')

        # eg:citizenstig/dvwa(get dvwa)
        cmd += image_port(ports, info)
        cmd += [name]
        print(cmd)
        container_id = subprocess.check_output(cmd)[0:6]
        container = Containers.query.filter_by(name=name).first_or_404()
        container.container_id = container_id
        db.session.commit()
        db.session.close()
        return True
    except subprocess.CalledProcessError:
        return False


def image_port(ports, info):
    print('port:', ports)
    cmd = []
    # if set(ports) <= set('0123456789:,'):
    if ports != '':
        ports_asked = ports.split(',')
        for port in ports_asked:
            port = port.split(':')
            if is_port_free(port[0]):
                cmd.append('-p')
                cmd.append('{}:{}'.format(port[0], port[1]))
            else:
                prot_rand = random.randint(5000, 10000)
                cmd.append('-p')
                cmd.append('{}:{}'.format(prot_rand, port[1]))

    else:
        try:
            ports_asked = info[0]['Config']['ExposedPorts'].keys()
            ports_asked = [int(re.sub('[A-Za-z/]+', '', port))
                           for port in ports_asked]
        except KeyError:
            ports_asked = []

        for port in ports_asked:
            prot_rand = random.randint(5000, 10000)
            cmd.append('-p')
            cmd.append('{}:{}'.format(prot_rand, port))

    return cmd


def port_split(ports):
    port_list = []
    ports = ports.split(',')
    for port in ports:
        port_list.append(tuple(port.split(':')))


def image_delete(name):
    print('runing ' + sys._getframe().f_code.co_name + ' function')
    try:
        subprocess.call(['docker', 'image', 'rmi', name])
        return True
    except subprocess.CalledProcessError:
        return False


def container_start(container_id):
    print('runing ' + sys._getframe().f_code.co_name + ' function')
    try:
        cmd = ['docker', 'start', container_id]
        subprocess.call(cmd)
        return True
    except subprocess.CalledProcessError:
        return False


def container_stop(container_id):
    print('runing ' + sys._getframe().f_code.co_name + ' function')
    try:
        cmd = ['docker', 'stop', container_id]
        subprocess.call(cmd)
        return True
    except subprocess.CalledProcessError:
        return False


def container_delete(containner_status, container_id):
    print('runing ' + sys._getframe().f_code.co_name + ' function')
    if containner_status == 'running':
        container_stop(container_id)
    try:
        cmd = ['docker', 'rm', container_id]
        subprocess.call(cmd)
        return True
    except subprocess.CalledProcessError:
        return False
