# Copyright (c) 2021 Markus Falb
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# I took podman_container_lib.py
# Copyright (c) 2020 RedHat
# and modified it

from __future__ import (absolute_import, division, print_function)
import json  # noqa: F402
from distutils.version import LooseVersion  # noqa: F402

from ansible.module_utils._text import to_bytes, to_native  # noqa: F402
from ansible_collections.mafalb.containerimages.plugins.module_utils.podman.common import lower_keys

__metaclass__ = type

ARGUMENTS_SPEC_CONTAINER = dict(
    name=dict(required=True, type='str'),
    executable=dict(default='buildah', type='str'),
    podman_executable=dict(default='podman', type='str'),
    state=dict(type='str', default='present', choices=[
        'absent', 'present']),
    image=dict(type='str'),
    annotation=dict(type='dict'),
    authfile=dict(type='path'),
    blkio_weight=dict(type='int'),
    blkio_weight_device=dict(type='dict'),
    cap_add=dict(type='list', elements='str', aliases=['capabilities']),
    cap_drop=dict(type='list', elements='str'),
    cgroup_parent=dict(type='path'),
    cgroupns=dict(type='str'),
    cgroups=dict(type='str'),
    cidfile=dict(type='path'),
    env=dict(type='dict'),
    command=dict(type='raw'),
    debug=dict(type='bool', default=False),
    workdir=dict(type='str', aliases=['working_dir'])

)


def init_options():
    default = {}
    opts = ARGUMENTS_SPEC_CONTAINER
    for k, v in opts.items():
        if 'default' in v:
            default[k] = v['default']
        else:
            default[k] = None
    return default


def update_options(opts_dict, container):
    def to_bool(x):
        return str(x).lower() not in ['no', 'false']

    aliases = {}
    for k, v in ARGUMENTS_SPEC_CONTAINER.items():
        if 'aliases' in v:
            for alias in v['aliases']:
                aliases[alias] = k
    for k in list(container):
        if k in aliases:
            key = aliases[k]
            container[key] = container.pop(k)
        else:
            key = k
        if (ARGUMENTS_SPEC_CONTAINER[key]['type'] == 'list'
                and not isinstance(container[key], list)):
            opts_dict[key] = [container[key]]
        elif (ARGUMENTS_SPEC_CONTAINER[key]['type'] == 'bool'
              and not isinstance(container[key], bool)):
            opts_dict[key] = to_bool(container[key])
        elif (ARGUMENTS_SPEC_CONTAINER[key]['type'] == 'int'
              and not isinstance(container[key], int)):
            opts_dict[key] = int(container[key])
        else:
            opts_dict[key] = container[key]

    return opts_dict


def set_container_opts(input_vars):
    default_options_templ = init_options()
    options_dict = update_options(default_options_templ, input_vars)
    return options_dict


class BuildahModuleParams:
    """Creates list of arguments for Buildah CLI command.

       Arguments:
           action {str} -- action type from 'run', 'stop', 'create', 'delete',
                           'start', 'restart'
           params {dict} -- dictionary of module parameters

       """

    def __init__(self, action, params, buildah_version, module):
        self.params = params
        self.action = action
        self.buildah_version = buildah_version
        self.module = module

    def construct_command_from_params(self):
        """Create a buildah command from given module parameters.

        Returns:
           list -- list of byte strings for Popen command
        """
        if self.action in ['start', 'stop', 'delete', 'restart']:
            return self.start_stop_delete()
        if self.action in ['create', 'run']:
            cmd = ['--name', self.params['name']]
            all_param_methods = [func for func in dir(self)
                                 if callable(getattr(self, func))
                                 and func.startswith("addparam")]
            params_set = (i for i in self.params if self.params[i] is not None)
            for param in params_set:
                func_name = "_".join(["addparam", param])
                if func_name in all_param_methods:
                    cmd = getattr(self, func_name)(cmd)
            if self.params['image']:
                cmd.append('from')
                cmd.append(self.params['image'])
            if self.params['command']:
                if isinstance(self.params['command'], list):
                    cmd += self.params['command']
                else:
                    cmd += self.params['command'].split()
            return [to_bytes(i, errors='surrogate_or_strict') for i in cmd]

    def start_stop_delete(self):

        if self.action in ['stop', 'start', 'restart']:
            cmd = [self.action, self.params['name']]
            return [to_bytes(i, errors='surrogate_or_strict') for i in cmd]

        if self.action == 'delete':
            cmd = ['rm', self.params['name']]
            return [to_bytes(i, errors='surrogate_or_strict') for i in cmd]

    def check_version(self, param, minv=None, maxv=None):
        if minv and LooseVersion(minv) > LooseVersion(
                self.buildah_version):
            self.module.fail_json(msg="Parameter %s is supported from buildah "
                                  "version %s only! Current version is %s" % (
                                      param, minv, self.buildah_version))
        if maxv and LooseVersion(maxv) < LooseVersion(
                self.buildah_version):
            self.module.fail_json(msg="Parameter %s is supported till buildah "
                                  "version %s only! Current version is %s" % (
                                      param, minv, self.buildah_version))

    def addparam_annotation(self, c):
        for annotate in self.params['annotation'].items():
            c += ['--annotation', '='.join(annotate)]
        return c

    def addparam_authfile(self, c):
        return c + ['--authfile', self.params['authfile']]

    def addparam_blkio_weight(self, c):
        return c + ['--blkio-weight', self.params['blkio_weight']]

    def addparam_blkio_weight_device(self, c):
        for blkio in self.params['blkio_weight_device'].items():
            c += ['--blkio-weight-device', ':'.join(blkio)]
        return c

    def addparam_cap_add(self, c):
        for cap_add in self.params['cap_add']:
            c += ['--cap-add', cap_add]
        return c

    def addparam_cap_drop(self, c):
        for cap_drop in self.params['cap_drop']:
            c += ['--cap-drop', cap_drop]
        return c

    def addparam_cgroups(self, c):
        self.check_version('--cgroups', minv='1.6.0')
        return c + ['--cgroups=%s' % self.params['cgroups']]

    def addparam_cgroupns(self, c):
        self.check_version('--cgroupns', minv='1.6.2')
        return c + ['--cgroupns=%s' % self.params['cgroupns']]

    def addparam_cgroup_parent(self, c):
        return c + ['--cgroup-parent', self.params['cgroup_parent']]

    def addparam_cidfile(self, c):
        return c + ['--cidfile', self.params['cidfile']]

    def addparam_conmon_pidfile(self, c):
        return c + ['--conmon-pidfile', self.params['conmon_pidfile']]

    def addparam_cpu_period(self, c):
        return c + ['--cpu-period', self.params['cpu_period']]

    def addparam_cpu_rt_period(self, c):
        return c + ['--cpu-rt-period', self.params['cpu_rt_period']]

    def addparam_cpu_rt_runtime(self, c):
        return c + ['--cpu-rt-runtime', self.params['cpu_rt_runtime']]

    def addparam_cpu_shares(self, c):
        return c + ['--cpu-shares', self.params['cpu_shares']]

    def addparam_cpus(self, c):
        return c + ['--cpus', self.params['cpus']]

    def addparam_cpuset_cpus(self, c):
        return c + ['--cpuset-cpus', self.params['cpuset_cpus']]

    def addparam_cpuset_mems(self, c):
        return c + ['--cpuset-mems', self.params['cpuset_mems']]

    def addparam_detach(self, c):
        return c + ['--detach=%s' % self.params['detach']]

    def addparam_detach_keys(self, c):
        return c + ['--detach-keys', self.params['detach_keys']]

    def addparam_device(self, c):
        for dev in self.params['device']:
            c += ['--device', dev]
        return c

    def addparam_device_read_bps(self, c):
        for dev in self.params['device_read_bps']:
            c += ['--device-read-bps', dev]
        return c

    def addparam_device_read_iops(self, c):
        for dev in self.params['device_read_iops']:
            c += ['--device-read-iops', dev]
        return c

    def addparam_device_write_bps(self, c):
        for dev in self.params['device_write_bps']:
            c += ['--device-write-bps', dev]
        return c

    def addparam_device_write_iops(self, c):
        for dev in self.params['device_write_iops']:
            c += ['--device-write-iops', dev]
        return c

    def addparam_dns(self, c):
        return c + ['--dns', ','.join(self.params['dns'])]

    def addparam_dns_option(self, c):
        return c + ['--dns-option', self.params['dns_option']]

    def addparam_dns_search(self, c):
        return c + ['--dns-search', self.params['dns_search']]

    def addparam_entrypoint(self, c):
        return c + ['--entrypoint', self.params['entrypoint']]

    def addparam_env(self, c):
        for env_value in self.params['env'].items():
            c += ['--env',
                  b"=".join([to_bytes(k, errors='surrogate_or_strict')
                             for k in env_value])]
        return c

    def addparam_env_file(self, c):
        return c + ['--env-file', self.params['env_file']]

    def addparam_env_host(self, c):
        self.check_version('--env-host', minv='1.5.0')
        return c + ['--env-host=%s' % self.params['env_host']]

    # Add your own args for buildah command
    def addparam_cmd_args(self, c):
        return c + self.params['cmd_args']


class BuildahDefaults:
    def __init__(self, image_info, buildah_version):
        self.version = buildah_version
        self.image_info = image_info
        self.defaults = {
            "workdir": self.image_info['docker']['config'].get('workingdir', '/'),
        }

    def default_dict(self):
        # make here any changes to self.defaults related to buildah version
        # https://github.com/containers/libpod/pull/5669
        return self.defaults


class BuildahContainerDiff:
    def __init__(self, module, module_params, info, image_info, buildah_version):
        self.module = module
        self.module_params = module_params
        self.version = buildah_version
        self.default_dict = None
        self.info = lower_keys(info)
        self.image_info = lower_keys(image_info)
        self.params = self.defaultize()
        self.diff = {'before': {}, 'after': {}}
        self.non_idempotent = {}

    def defaultize(self):
        params_with_defaults = {}
        self.default_dict = BuildahDefaults(
            self.image_info, self.version).default_dict()
        for p in self.module_params:
            if self.module_params[p] is None and p in self.default_dict:
                params_with_defaults[p] = self.default_dict[p]
            else:
                params_with_defaults[p] = self.module_params[p]
        return params_with_defaults

    def _diff_update_and_compare(self, param_name, before, after):
        if before != after:
            self.diff['before'].update({param_name: before})
            self.diff['after'].update({param_name: after})
            return True
        return False

    def diffparam_annotation(self):
        before = self.info['config']['annotations'] or {}
        after = before.copy()
        if self.module_params['annotation'] is not None:
            after.update(self.params['annotation'])
        return self._diff_update_and_compare('annotation', before, after)

    def diffparam_env_host(self):
        # It's impossible to get from inspest, recreate it if not default
        before = False
        after = self.params['env_host']
        return self._diff_update_and_compare('env_host', before, after)

    def diffparam_blkio_weight(self):
        before = self.info['hostconfig']['blkioweight']
        after = self.params['blkio_weight']
        return self._diff_update_and_compare('blkio_weight', before, after)

    def diffparam_blkio_weight_device(self):
        before = self.info['hostconfig']['blkioweightdevice']
        if before == [] and self.module_params['blkio_weight_device'] is None:
            after = []
        else:
            after = self.params['blkio_weight_device']
        return self._diff_update_and_compare('blkio_weight_device', before, after)

    def diffparam_cap_add(self):
        before = (self.info['DefaultCapabilities']
                  + self.info['AddCapabilities']
                  - self.info['DropCapabilities']
                  ) or []
        before = [i.lower() for i in before]
        after = []
        if self.module_params['cap_add'] is not None:
            for cap in self.module_params['cap_add']:
                cap = cap.lower()
                cap = cap if cap.startswith('cap_') else 'cap_' + cap
                after.append(cap)
        after += before
        before, after = sorted(list(set(before))), sorted(list(set(after)))
        return self._diff_update_and_compare('cap_add', before, after)

    def diffparam_cap_drop(self):
        before = (self.info['DefaultCapabilities']
                  + self.info['AddCapabilities']
                  - self.info['DropCapabilities']
                  ) or []
        before = [i.lower() for i in before]
        after = before[:]
        if self.module_params['cap_drop'] is not None:
            for cap in self.module_params['cap_drop']:
                cap = cap.lower()
                cap = cap if cap.startswith('cap_') else 'cap_' + cap
                if cap in after:
                    after.remove(cap)
        before, after = sorted(list(set(before))), sorted(list(set(after)))
        return self._diff_update_and_compare('cap_drop', before, after)

    def diffparam_cgroup_parent(self):
        before = self.info['hostconfig']['cgroupparent']
        after = self.params['cgroup_parent']
        if after is None:
            after = before
        return self._diff_update_and_compare('cgroup_parent', before, after)

    def diffparam_cgroups(self):
        # Cgroups output is not supported in all versions
        if 'cgroups' in self.info['hostconfig']:
            before = self.info['hostconfig']['cgroups']
            after = self.params['cgroups']
            return self._diff_update_and_compare('cgroups', before, after)
        return False

    def diffparam_cidfile(self):
        before = self.info['hostconfig']['containeridfile']
        after = self.params['cidfile']
        labels = self.info['config']['labels'] or {}
        # Ignore cidfile that is coming from systemd files
        # https://github.com/containers/ansible-podman-collections/issues/276
        if 'podman_systemd_unit' in labels:
            after = before
        return self._diff_update_and_compare('cidfile', before, after)

    # Limited idempotency, it can't guess default values
    def diffparam_env(self):
        env_before = self.info['ociv1']['config']['env'] or {}
        before = {i.split("=")[0]: "=".join(i.split("=")[1:])
                  for i in env_before}
        after = before.copy()
        if self.params['env']:
            after.update({k: str(v) for k, v in self.params['env'].items()})
        return self._diff_update_and_compare('env', before, after)

    def diffparam_image(self):
        before_id = self.info['fromimageid']
        after_id = self.image_info['fromimageid']
        if before_id == after_id:
            return self._diff_update_and_compare('image', before_id, after_id)
        before = self.info['config']['image']
        after = self.params['image']
        mode = self.params['image_strict']
        if mode is None or not mode:
            # In a idempotency 'lite mode' assume all images from different registries are the same
            before = before.replace(":latest", "")
            after = after.replace(":latest", "")
            before = before.split("/")[-1]
            after = after.split("/")[-1]
        else:
            return self._diff_update_and_compare('image', before_id, after_id)
        return self._diff_update_and_compare('image', before, after)

    def diffparam_workdir(self):
        before = self.info['docker']['config']['workingdir']
        after = self.params['workdir']
        return self._diff_update_and_compare('workdir', before, after)

    def is_different(self):
        diff_func_list = [func for func in dir(self)
                          if callable(getattr(self, func)) and func.startswith(
                              "diffparam")]
        fail_fast = not bool(self.module._diff)
        different = False
        for func_name in diff_func_list:
            dff_func = getattr(self, func_name)
            if dff_func():
                if fail_fast:
                    return True
                different = True
        # Check non idempotent parameters
        for p in self.non_idempotent:
            if self.module_params[p] is not None and self.module_params[p] not in [{}, [], '']:
                different = True
        return different


def ensure_image_exists(module, image, module_params):
    """If image is passed, ensure it exists, if not - pull it or fail.

    Arguments:
        module {obj} -- ansible module object
        image {str} -- name of image

    Returns:
        list -- list of image actions - if it pulled or nothing was done
    """
    image_actions = []
    module_exec = module_params['podman_executable']
    if not image:
        return image_actions
    rc, out, err = module.run_command([module_exec, 'image', 'exists', image])
    if rc == 0:
        return image_actions
    rc, out, err = module.run_command([module_exec, 'pull', image])
    if rc != 0:
        module.fail_json(msg="Can't pull image %s" % image, stdout=out,
                         stderr=err)
    image_actions.append("pulled image %s" % image)
    return image_actions


class BuildahContainer:
    """Perform container tasks.

    Manages buildah container, inspects it and checks its current state
    """

    def __init__(self, module, name, module_params):
        """Initialize BuildahContainer class.

        Arguments:
            module {obj} -- ansible module object
            name {str} -- name of container
        """

        self.module = module
        self.module_params = module_params
        self.name = name
        self.stdout, self.stderr = '', ''
        self.info = self.get_info()
        self.version = self._get_buildah_version()
        self.diff = {}
        self.actions = []

    @property
    def exists(self):
        """Check if container exists."""
        return bool(self.info != {})

    @property
    def different(self):
        """Check if container is different."""
        diffcheck = BuildahContainerDiff(
            self.module,
            self.module_params,
            self.info,
            self.get_image_info(),
            self.version)
        is_different = diffcheck.is_different()
        diffs = diffcheck.diff
        if self.module._diff and is_different and diffs['before'] and diffs['after']:
            self.diff['before'] = "\n".join(
                ["%s - %s" % (k, v) for k, v in sorted(
                    diffs['before'].items())]) + "\n"
            self.diff['after'] = "\n".join(
                ["%s - %s" % (k, v) for k, v in sorted(
                    diffs['after'].items())]) + "\n"
        return is_different

    @property
    def running(self):
        """Return True if container is running now."""
        return self.exists and self.info['State']['Running']

    @property
    def stopped(self):
        """Return True if container exists and is not running now."""
        return self.exists and not self.info['State']['Running']

    def get_info(self):
        """Inspect container and gather info about it."""
        # pylint: disable=unused-variable
        rc, out, err = self.module.run_command(
            [self.module_params['executable'], b'inspect', self.name])
        return json.loads(out) if rc == 0 else {}

    def get_image_info(self):
        """Inspect container image and gather info about it."""
        # pylint: disable=unused-variable
        rc, out, err = self.module.run_command([self.module_params['executable'], b'inspect',
                                               '--type', 'image', self.module_params['image']])
        self.module.log("BUILDAH-CONTAINER-DEBUG: %s" % type(out))
        return json.loads(out) if rc == 0 else {}

    def _get_buildah_version(self):
        # pylint: disable=unused-variable
        rc, out, err = self.module.run_command(
            [self.module_params['executable'], b'--version'])
        if rc != 0 or not out or "version" not in out:
            self.module.fail_json(msg="%s run failed!" %
                                  self.module_params['executable'])
        return out.split("version")[1].strip()

    def _perform_action(self, action):
        """Perform action with container.

        Arguments:
            action {str} -- action to perform - start, create, stop, run,
                            delete, restart
        """
        b_command = BuildahModuleParams(action,
                                        self.module_params,
                                        self.version,
                                        self.module,
                                        ).construct_command_from_params()
        full_cmd = " ".join([self.module_params['executable']] +
                            [to_native(i) for i in b_command])
        self.actions.append(full_cmd)
        if self.module.check_mode:
            self.module.log(
                "BUILDAH-CONTAINER-DEBUG (check_mode): %s" % full_cmd)
        else:
            self.module.log("BUILDAH-CONTAINER-DEBUG: %s" % full_cmd)
            rc, out, err = self.module.run_command(
                [self.module_params['executable']] + b_command,
                expand_user_and_vars=False)
            self.module.log("BUILDAH-CONTAINER-DEBUG: %s" % full_cmd)
            if self.module_params['debug']:
                self.module.log("BUILDAH-CONTAINER-DEBUG STDOUT: %s" % out)
                self.module.log("BUILDAH-CONTAINER-DEBUG STDERR: %s" % err)
                self.module.log("BUILDAH-CONTAINER-DEBUG RC: %s" % rc)
            self.stdout = out
            self.stderr = err
            if rc != 0:
                self.module.fail_json(
                    msg="Can't %s container %s" % (action, self.name),
                    stdout=out, stderr=err)

    def run(self):
        """Run the container."""
        self._perform_action('run')

    def delete(self):
        """Delete the container."""
        self._perform_action('delete')

    def stop(self):
        """Stop the container."""
        self._perform_action('stop')

    def start(self):
        """Start the container."""
        self._perform_action('start')

    def restart(self):
        """Restart the container."""
        self._perform_action('restart')

    def create(self):
        """Create the container."""
        self._perform_action('create')

    def recreate(self):
        """Recreate the container."""
        if self.running:
            self.stop()
        self.delete()
        self.create()

    def recreate_run(self):
        """Recreate and run the container."""
        if self.running:
            self.stop()
        self.delete()
        self.run()


class BuildahManager:
    """Module manager class.

    Defines according to parameters what actions should be applied to container
    """

    def __init__(self, module, params):
        """Initialize BuildahManager class.

        Arguments:
            module {obj} -- ansible module object
        """

        self.module = module
        self.results = {
            'changed': False,
            'actions': [],
            'container': {},
        }
        self.module_params = params
        self.name = self.module_params['name']
        self.executable = \
            self.module.get_bin_path(self.module_params['executable'],
                                     required=True)
        self.image = self.module_params['image']
        image_actions = ensure_image_exists(
            self.module, self.image, self.module_params)
        self.results['actions'] += image_actions
        self.state = self.module_params['state']
        self.container = BuildahContainer(
            self.module, self.name, self.module_params)

    def update_container_result(self, changed=True):
        """Inspect the current container, update results with last info, exit.

        Keyword Arguments:
            changed {bool} -- whether any action was performed
                              (default: {True})
        """
        facts = self.container.get_info() if changed else self.container.info
        out, err = self.container.stdout, self.container.stderr
        self.results.update({'changed': changed, 'container': facts,
                             'buildah_actions': self.container.actions},
                            stdout=out, stderr=err)
        if self.container.diff:
            self.results.update({'diff': self.container.diff})
        if self.module.params['debug'] or self.module_params['debug']:
            self.results.update({'buildah_version': self.container.version})

    def make_started(self):
        """Run actions if desired state is 'started'."""
        if not self.image:
            if not self.container.exists:
                self.module.fail_json(msg='Cannot start container when image'
                                          ' is not specified!')
            if self.restart:
                self.container.restart()
                self.results['actions'].append('restarted %s' %
                                               self.container.name)
            else:
                self.container.start()
                self.results['actions'].append('started %s' %
                                               self.container.name)
            self.update_container_result()
            return
        if self.container.exists and self.restart:
            if self.container.running:
                self.container.restart()
                self.results['actions'].append('restarted %s' %
                                               self.container.name)
            else:
                self.container.start()
                self.results['actions'].append('started %s' %
                                               self.container.name)
            self.update_container_result()
            return
        if self.container.running and \
                (self.container.different or self.recreate):
            self.container.recreate_run()
            self.results['actions'].append('recreated %s' %
                                           self.container.name)
            self.update_container_result()
            return
        elif self.container.running and not self.container.different:
            if self.restart:
                self.container.restart()
                self.results['actions'].append('restarted %s' %
                                               self.container.name)
                self.update_container_result()
                return
            self.update_container_result(changed=False)
            return
        elif not self.container.exists:
            self.container.run()
            self.results['actions'].append('started %s' % self.container.name)
            self.update_container_result()
            return
        elif self.container.stopped and self.container.different:
            self.container.recreate_run()
            self.results['actions'].append('recreated %s' %
                                           self.container.name)
            self.update_container_result()
            return
        elif self.container.stopped and not self.container.different:
            self.container.start()
            self.results['actions'].append('started %s' % self.container.name)
            self.update_container_result()
            return

    def make_created(self):
        """Run actions if desired state is 'created'."""
        if not self.container.exists and not self.image:
            self.module.fail_json(msg='Cannot create container when image'
                                      ' is not specified!')
        if not self.container.exists:
            self.container.create()
            self.results['actions'].append('created %s' % self.container.name)
            self.update_container_result()
            return
        else:
            if (self.container.different):
                self.container.recreate()
                self.results['actions'].append('recreated %s' %
                                               self.container.name)
                if self.container.running:
                    self.container.start()
                    self.results['actions'].append('started %s' %
                                                   self.container.name)
                self.update_container_result()
                return
            self.update_container_result(changed=False)
            return

    def make_stopped(self):
        """Run actions if desired state is 'stopped'."""
        if not self.container.exists and not self.image:
            self.module.fail_json(msg='Cannot create container when image'
                                      ' is not specified!')
        if not self.container.exists:
            self.container.create()
            self.results['actions'].append('created %s' % self.container.name)
            self.update_container_result()
            return
        if self.container.stopped:
            self.update_container_result(changed=False)
            return
        elif self.container.running:
            self.container.stop()
            self.results['actions'].append('stopped %s' % self.container.name)
            self.update_container_result()
            return

    def make_absent(self):
        """Run actions if desired state is 'absent'."""
        if not self.container.exists:
            self.results.update({'changed': False})
        elif self.container.exists:
            self.container.delete()
            self.results['actions'].append('deleted %s' % self.container.name)
            self.results.update({'changed': True})
        self.results.update({'container': {},
                             'buildah_actions': self.container.actions})

    def execute(self):
        """Execute the desired action according to map of actions & states."""
        states_map = {
            'present': self.make_created,
            'absent': self.make_absent,
            'created': self.make_created,
        }
        process_action = states_map[self.state]
        process_action()
        return self.results
