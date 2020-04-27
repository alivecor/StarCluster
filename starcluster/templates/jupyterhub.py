# Copyright 2018 Daniel Treiman
#
# This file is part of StarCluster.
#
# StarCluster is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# StarCluster is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with StarCluster. If not, see <http://www.gnu.org/licenses/>.


jupyterhub_config_template = """
from oauthenticator.google import GoogleOAuthenticator
from batchspawner import GridengineSpawner
from wrapspawner import ProfilesSpawner
import os
import socket
import subprocess
import xml.etree.ElementTree


# Get hub IP address.  This is not the public IP, it is the private IP in the VPC which is visible to
# all nodes in the cluster.
hub_ip_address = socket.gethostbyname(socket.gethostname())

## Allow named single-user servers per user
c.JupyterHub.allow_named_servers = True

c.JupyterHub.authenticator_class = GoogleOAuthenticator

c.Authenticator.whitelist = set([%(user_whitelist)s])
c.Authenticator.admin_users = set([%(admin_whitelist)s])

c.GoogleOAuthenticator.oauth_callback_url = '%(oauth_callback_url)s'
c.GoogleOAuthenticator.client_id = '%(oauth_client_id)s'
c.GoogleOAuthenticator.client_secret = '%(oauth_client_secret)s'

if %(hosted_domain)s is not None:
    c.GoogleOAuthenticator.hosted_domain = %(hosted_domain)s
    c.GoogleOAuthenticator.login_service = %(login_service)s

## Whether to shutdown the proxy when the Hub shuts down.
c.JupyterHub.cleanup_proxy = True

## Whether to shutdown single-user servers when the Hub shuts down.
c.JupyterHub.cleanup_servers = True

## Number of days for a login cookie to be valid. Default is two weeks.
c.JupyterHub.cookie_max_age_days = 14

## The ip address for the Hub process to *bind* to.
#  
#  See `hub_connect_ip` for cases where the bind and connect address should
#  differ.
c.JupyterHub.hub_ip = hub_ip_address

## The port for the Hub process
c.JupyterHub.hub_port = 8081

## The public facing ip of the whole application (the proxy)
c.JupyterHub.ip = hub_ip_address

c.JupyterHub.hub_connect_ip = hub_ip_address

## Specify path to a logo image to override the Jupyter logo in the banner.
#c.JupyterHub.logo_file = ''

## File to write PID Useful for daemonizing jupyterhub.
#c.JupyterHub.pid_file = ''

## The public facing port of the proxy
c.JupyterHub.port = 8000


# Monkey patches home directory default.
def _req_homedir_default(self):
    return os.path.join('%(homedir)s', self.user.name)
GridengineSpawner._req_homedir_default = _req_homedir_default

c.JupyterHub.spawner_class = ProfilesSpawner

c.Spawner.cmd = ['/usr/local/bin/jupyter-labhub']
c.Spawner.default_url = '/user/{username}/lab'
c.Spawner.notebook_dir = '%(notebook_dir)s'
c.Spawner.environment = dict(
    SGE_ROOT='/opt/sge6',
    SGE_CELL='default',
    SGE_EXECD_PORT='63232',
    SGE_QMASTER_PORT='63231',
    SGE_CLUSTER_NAME='starcluster',
#    XDG_RUNTIME_DIR='/run/user/1001',
    XDG_RUNTIME_DIR='',
    JUPYTER_ENABLE_LAB='yes'
)
c.Spawner.http_timeout = 120


QHOST_PATH = '/opt/sge6/bin/linux-x64/qhost'

ENV = dict(os.environ)
ENV['HOME'] = '/home/sgeadmin'
ENV['SGE_CELL'] = 'default'
ENV['SGE_EXECD_PORT'] = '63232'
ENV['SGE_QMASTER_PORT'] = '63231'
ENV['SGE_ROOT'] = '/opt/sge6'
ENV['SGE_CLUSTER_NAME'] = 'starcluster'

command = '{} -xml -q'.format(QHOST_PATH)
result_xml = subprocess.check_output([command], env=ENV, shell=True)
hosts_element = xml.etree.ElementTree.fromstring(result_xml)
node_profiles = []
for host_element in hosts_element:
    if host_element.get('name') == 'global':
        continue
    name = host_element.get('name')
    queues = []
    for host_value in host_element:
        if host_value.tag == 'queue':
            queue_name = host_value.get('name')
            slots = 0
            for qv in host_value:
                if qv.get('name') == 'slots':
                    slots = int(qv.text)
            if slots > 0:
                queues.append(queue_name)
    queue = 'cpu.q'
    if 'mem.q' in queues:
        queue = 'mem.q'
    if 'gpu.q' in queues:
        queue = 'gpu.q'
    queue_type = queue.split('.')[0]
    node_queue = '{}@{}'.format(queue, name)
    node_profiles.append(
        (u'{} ({})'.format(name, queue_type), u'{}_{}'.format(queue.replace('.', '_'), name.replace('.', '_')), GridengineSpawner, dict(
            batch_submit_cmd='sudo -u {{username}} -E /opt/sge6/bin/linux-x64/qsub -q {}'.format(node_queue),
            batch_query_cmd='sudo -u {{username}} -E /opt/sge6/bin/linux-x64/qstat -q {} -xml'.format(node_queue),
            batch_cancel_cmd='sudo -u {username} -E /opt/sge6/bin/linux-x64/qdel {job_id}',
            hub_connect_ip=hub_ip_address))
    )


c.ProfilesSpawner.profiles = [
    (u'General Purpose (1 CPU)', u'cpu_lab', GridengineSpawner, dict(
        batch_submit_cmd='sudo -u {username} -E /opt/sge6/bin/linux-x64/qsub -q cpu.q',
        batch_query_cmd='sudo -u {username} -E /opt/sge6/bin/linux-x64/qstat -q cpu.q -xml',
        batch_cancel_cmd='sudo -u {username} -E /opt/sge6/bin/linux-x64/qdel {job_id}',
        hub_connect_ip=hub_ip_address
    )),
    (u'GPU Compute (4 CPUs, 1 GPU)', u'gpu_lab', GridengineSpawner, dict(
        batch_submit_cmd='sudo -u {username} -E /opt/sge6/bin/linux-x64/qsub -q gpu.q',
        batch_query_cmd='sudo -u {username} -E /opt/sge6/bin/linux-x64/qstat -q gpu.q -xml',
        batch_cancel_cmd='sudo -u {username} -E /opt/sge6/bin/linux-x64/qdel {job_id}',
        hub_connect_ip=hub_ip_address
    )),
    (u'Large Memory CPU', u'mem_lab', GridengineSpawner, dict(
        batch_submit_cmd='sudo -u {username} -E /opt/sge6/bin/linux-x64/qsub -q mem.q',
        batch_query_cmd='sudo -u {username} -E /opt/sge6/bin/linux-x64/qstat -q mem.q -xml',
        batch_cancel_cmd='sudo -u {username} -E /opt/sge6/bin/linux-x64/qdel {job_id}',
        hub_connect_ip=hub_ip_address
    ))
] + node_profiles

## Path to SSL certificate file for the public facing interface of the proxy
#  
#  When setting this, you should also set ssl_key
#c.JupyterHub.ssl_cert = ''

## Path to SSL key file for the public facing interface of the proxy
#  
#  When setting this, you should also set ssl_cert
#c.JupyterHub.ssl_key = ''

## Host to send statsd metrics to
#c.JupyterHub.statsd_host = ''

## Port on which to send statsd metrics about the hub
#c.JupyterHub.statsd_port = 8125

## Prefix to use for all metrics sent by jupyterhub to statsd
#c.JupyterHub.statsd_prefix = 'jupyterhub'

## Run single-user servers on subdomains of this host.
#  
#  This should be the full `https://hub.domain.tld[:port]`.
#  
#  Provides additional cross-site protections for javascript served by single-
#  user servers.
#  
#  Requires `<username>.hub.domain.tld` to resolve to the same host as
#  `hub.domain.tld`.
#  
#  In general, this is most easily achieved with wildcard DNS.
#  
#  When using SSL (i.e. always) this also requires a wildcard SSL certificate.
#c.JupyterHub.subdomain_host = ''

## Whitelist of environment variables for the single-user server to inherit from
#  the JupyterHub process.
#c.Spawner.env_keep = ['PATH', 'PYTHONPATH', 'CONDA_ROOT', 'CONDA_DEFAULT_ENV', 'VIRTUAL_ENV', 'LANG', 'LC_ALL']

## The IP address (or hostname) the single-user server should listen on.
#  
#  The JupyterHub proxy implementation should be able to send packets to this
#  interface.
#c.Spawner.ip = ''

"""


jupyterhub_service_template= """
[Unit]
Description=Jupyterhub

[Service]
User=root
Environment="PATH=/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/opt/anaconda3/bin"
Environment="SGE_ROOT=/opt/sge6"
Environment="SGE_CELL=default"
Environment="SGE_EXECD_PORT=63232"
Environment="SGE_QMASTER_PORT=63231"
Environment="SGE_CLUSTER_NAME=starcluster"
Environment="XDG_RUNTIME_DIR=/run/user/1001"
ExecStart=/usr/local/bin/jupyterhub -f %(jupyterhub_config)s

[Install]
WantedBy=multi-user.target
"""
