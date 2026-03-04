import time

from cli.exceptions import AnsiblePlaybookExecutionError, ConfigError
from cli.ops.cephadm_ansible import (
    autoload_registry_details,
    exec_ceph_config,
    exec_ceph_orch_apply,
    exec_ceph_orch_daemon,
    exec_ceph_orch_host,
    exec_cephadm_registry_login,
)
from cli.utilities.operations import wait_for_osd_daemon_state
from utility.log import Log

log = Log(__name__)

# Retries for ceph_orch_daemon stop/start: the ansible module validates daemon
# status with a fixed number of retries; under load status may update slowly.
CEPH_ORCH_DAEMON_STATE_RETRIES = 3
CEPH_ORCH_DAEMON_STATE_RETRY_DELAY = 45


def run(ceph_cluster, **kwargs):
    """Verify cephadm ansible modules"""
    # Get cluster config
    installer, nodes = (
        ceph_cluster.get_nodes(role="installer")[0],
        ceph_cluster.get_nodes(),
    )

    # Get config specs
    config = kwargs.get("config")

    # Get build details
    ibm_build = config.get("ibm_build", False)

    # Get config specs
    config = kwargs.get("config")

    for module in config.keys():
        # Check for module
        if module not in [
            "ceph_orch_host",
            "ceph_orch_apply",
            "ceph_config",
            "ceph_orch_daemon",
            "cephadm_registry_login",
        ]:
            continue

        # Get module configs
        module_config = config.get(module)

        # Get bootstrap module configs
        playbook = module_config.get("playbook")
        if not playbook:
            raise ConfigError("Mandatory parameter 'playbook' not provided")

        module_args = module_config.get("module_args", {})

        if module == "ceph_orch_host":
            # Eexecute `ceph_orch_host` module playbook
            exec_ceph_orch_host(installer, nodes, playbook, **module_args)

        elif module == "ceph_orch_apply":
            # Eexecute `ceph_orch_apply` module playbook
            exec_ceph_orch_apply(installer, playbook, **module_args)

        elif module == "ceph_config":
            # Eexecute `ceph_config` module playbook
            exec_ceph_config(installer, playbook, **module_args)

        elif module == "ceph_orch_daemon":
            # Wait for OSD to be expected state
            if module_config.get("wait_for_state") and module_args.get(
                "daemon_type"
            ) in ["osd"]:
                wait_for_osd_daemon_state(
                    installer,
                    module_args.get("daemon_id"),
                    module_config.get("wait_for_state"),
                )

            # Explicitly wait for 60 sec
            time.sleep(60)

            # Execute `ceph_orch_daemon` module playbook. For stop/start/restart,
            # retry in case the module's status validation times out (e.g. "Status
            # for osd.N isn't reported as expected") while the daemon actually did
            # change state.
            state = module_args.get("state")
            if state in ("stopped", "started", "restarted"):
                last_error = None
                for attempt in range(CEPH_ORCH_DAEMON_STATE_RETRIES):
                    try:
                        exec_ceph_orch_daemon(installer, playbook, **module_args)
                        break
                    except AnsiblePlaybookExecutionError as e:
                        last_error = e
                        if attempt < CEPH_ORCH_DAEMON_STATE_RETRIES - 1:
                            log.info(
                                "ceph_orch_daemon playbook failed (attempt %s/%s), "
                                "retrying in %ss",
                                attempt + 1,
                                CEPH_ORCH_DAEMON_STATE_RETRIES,
                                CEPH_ORCH_DAEMON_STATE_RETRY_DELAY,
                            )
                            time.sleep(CEPH_ORCH_DAEMON_STATE_RETRY_DELAY)
                        else:
                            raise last_error
            else:
                exec_ceph_orch_daemon(installer, playbook, **module_args)

        elif module == "cephadm_registry_login":
            # Check for registry details
            if module_config.get("autoload_registry_details"):
                module_args.update(autoload_registry_details(ibm_build))

            exec_cephadm_registry_login(installer, playbook, **module_args)

    return 0
