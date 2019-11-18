# Ansible Collection - mafalb.docker [![Build Status](https://travis-ci.com/mafalb/ansible-collection-containers.svg?branch=master)](https://travis-ci.com/mafalb/ansible-collection-containers)

## Basic Usage

```ansible
- hosts: localhost
  roles:
    - role: mafalb.docker/docker
```

to install the distribution provided docker daemon

or

```ansible
- hosts: localhost
  roles:
    - role: mafalb.docker/docker
      docker_package: docker-ce
```

to install docker-ce provided by Docker Inc.

or

```ansible
hosts: localhost
  roles:
    - role: mafalb.docker/python
```

to install the [Docker SDK for Python](https://docker-py.readthedocs.io/en/stable/).
For instance, this is a requirement for ansible nodes if you use [docker_image](https://docs.ansible.com/ansible/latest/modules/docker_container_module.html#docker-container-module) or  [docker_container](https://docs.ansible.com/ansible/latest/modules/docker_container_module.html#docker-container-module).

## Variables

With many distributions you have a choice which docker you want. Some distributions ship with docker packages, but you could choose to *not* install the distribution provided docker. Sometimes the distribution docker seems too outdated, or maybe docker is preinstalled in a CI environment). My docker module supports the docker-ce packages provided by Docker Inc. as an alternative, docker-ee is not supported.

*if* your distribution does provide docker, and you want to install docker-ce, you have to set this variable.  
*if* your distribution does not provide docker, you **don't** have to set this variable. There is only one choice anyways.

`docker_package: docker-ce` # set this if you want to install docker-ce from Docker Inc.

## Author

This ansible collection was created by Markus Falb

## License

GPLv3
