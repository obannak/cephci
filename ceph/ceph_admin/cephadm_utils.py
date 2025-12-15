def redeploy_monitoring_services_helper(
    cephadm,
    cluster,
    image_registry,
    specs,
):
    """
    Helper to redeploy monitoring services using the correct container images.

    This function should be used after a minimal Ceph bootstrap where monitoring
    services may have been deployed with default/incorrect images (e.g., cp.icr.io).

    Supports:
    - Standard Ceph monitoring services that require container images:
        prometheus, grafana, alertmanager
    - Other services such as node-exporter, crash, or custom services

    Steps:
    1. Remove existing monitoring services (best-effort)
    2. Set mgr/cephadm container image configs for applicable services
    3. Verify image configs were applied
    4. Reapply all services using `apply_spec`
    """

    # Services that require container image configuration
    services_with_images = {
        "prometheus": "mgr/cephadm/container_image_prometheus",
        "grafana": "mgr/cephadm/container_image_grafana",
        "alertmanager": "mgr/cephadm/container_image_alertmanager",
    }

    # Combine all services for removal (including non-image-based)
    all_services = list(services_with_images.keys()) + ["node-exporter", "crash"]

    # Step 1: Remove existing services
    cephadm.log.info(f"[{cluster}] Removing existing monitoring services (best-effort)")
    for svc in all_services:
        cephadm.log.debug(f"[{cluster}] Removing service: {svc}")
        cephadm.orch.remove(service_name=svc, cluster=cluster, ignore_errors=True)

    # Step 2: Set container image configs for services that require them
    cephadm.log.info(f"[{cluster}] Setting mgr/cephadm container image configs")
    for svc, config_key in services_with_images.items():
        cephadm.log.debug(f"[{cluster}] Setting {svc} image: {image_registry}/{svc}")
        cephadm.shell(f"ceph config set {config_key} {image_registry}/{svc}", cluster=cluster)

    # Step 3: Verify mgr configs
    cephadm.log.info(f"[{cluster}] Verifying mgr/cephadm container image configuration")
    cephadm.shell("ceph config dump | grep mgr/cephadm/container_image", cluster=cluster)

    # Step 4: Reapply all services using apply_spec
    cephadm.log.info(f"[{cluster}] Reapplying monitoring services using apply_spec")
    cephadm.orch.apply_spec(specs=specs, validate=True, cluster=cluster)
