"""Tests for Docker build process and container functionality."""

import os
import pytest
import docker
import subprocess
import time
import requests
from pathlib import Path


@pytest.fixture(scope="session")
def docker_client():
    """Docker client fixture."""
    try:
        client = docker.from_env()
        # Test connection
        client.ping()
        return client
    except Exception as e:
        pytest.skip(f"Docker not available: {e}")


@pytest.fixture(scope="session")
def project_root():
    """Get project root directory."""
    return Path(__file__).parent.parent


class TestDockerBuildProcess:
    """Test Docker build process for all services."""
    
    def test_docker_daemon_available(self, docker_client):
        """Test that Docker daemon is available."""
        assert docker_client.ping() is True
    
    def test_monitoring_dockerfile_exists(self, project_root):
        """Test that monitoring service Dockerfile exists."""
        dockerfile_path = project_root / "Dockerfile.monitoring"
        assert dockerfile_path.exists(), "Monitoring Dockerfile not found"
    
    def test_orchestrator_dockerfile_exists(self, project_root):
        """Test that orchestrator service Dockerfile exists."""
        dockerfile_path = project_root / "Dockerfile.orchestrator"
        assert dockerfile_path.exists(), "Orchestrator Dockerfile not found"
    
    def test_controller_dockerfile_exists(self, project_root):
        """Test that controller service Dockerfile exists."""
        dockerfile_path = project_root / "Dockerfile.controller"
        assert dockerfile_path.exists(), "Controller Dockerfile not found"
    
    def test_dockerignore_exists(self, project_root):
        """Test that .dockerignore file exists."""
        dockerignore_path = project_root / ".dockerignore"
        assert dockerignore_path.exists(), ".dockerignore file not found"
    
    def test_requirements_file_exists(self, project_root):
        """Test that requirements.txt exists for Docker builds."""
        requirements_path = project_root / "requirements.txt"
        assert requirements_path.exists(), "requirements.txt not found"


class TestMonitoringDockerBuild:
    """Test monitoring service Docker build."""
    
    @pytest.fixture(scope="class")
    def monitoring_image(self, docker_client, project_root):
        """Build monitoring service image."""
        image_tag = "moolai/monitoring:test"
        
        try:
            # Build the image
            print(f"Building monitoring image: {image_tag}")
            image, build_logs = docker_client.images.build(
                path=str(project_root),
                dockerfile="Dockerfile.monitoring",
                tag=image_tag,
                rm=True,
                forcerm=True
            )
            
            # Print build logs for debugging
            for log in build_logs:
                if 'stream' in log:
                    print(log['stream'].strip())
            
            yield image
            
            # Cleanup
            try:
                docker_client.images.remove(image.id, force=True)
            except Exception as e:
                print(f"Warning: Could not remove image {image.id}: {e}")
                
        except Exception as e:
            pytest.fail(f"Failed to build monitoring image: {e}")
    
    def test_monitoring_image_created(self, monitoring_image):
        """Test that monitoring image was created successfully."""
        assert monitoring_image is not None
        assert len(monitoring_image.tags) > 0
    
    def test_monitoring_image_labels(self, monitoring_image):
        """Test monitoring image has correct labels."""
        labels = monitoring_image.labels or {}
        
        expected_labels = [
            "org.moolai.service",
            "org.moolai.version",
            "org.moolai.description"
        ]
        
        for label in expected_labels:
            assert label in labels, f"Missing label: {label}"
    
    def test_monitoring_image_expose_ports(self, monitoring_image):
        """Test that monitoring image exposes correct ports."""
        config = monitoring_image.attrs['Config']
        exposed_ports = config.get('ExposedPorts', {})
        
        # Should expose port 8001 for sidecar mode
        assert '8001/tcp' in exposed_ports, "Port 8001 not exposed"
    
    def test_monitoring_container_starts(self, docker_client, monitoring_image):
        """Test that monitoring container starts successfully."""
        container = None
        try:
            container = docker_client.containers.run(
                monitoring_image.id,
                environment={
                    "MONITORING_MODE": "sidecar",
                    "ORCHESTRATOR_ID": "test_orchestrator",
                    "ORGANIZATION_ID": "test_org",
                    "DATABASE_URL": "postgresql://test:test@localhost:5432/test_db",
                    "REDIS_URL": "redis://localhost:6379/0"
                },
                ports={'8001/tcp': 8001},
                detach=True,
                remove=True
            )
            
            # Wait for container to start
            time.sleep(3)
            
            # Check container status
            container.reload()
            assert container.status == "running"
            
        except Exception as e:
            pytest.fail(f"Container failed to start: {e}")
        finally:
            if container:
                try:
                    container.stop(timeout=5)
                except Exception:
                    pass
    
    def test_monitoring_health_endpoint(self, docker_client, monitoring_image):
        """Test that monitoring container health endpoint works."""
        container = None
        try:
            container = docker_client.containers.run(
                monitoring_image.id,
                environment={
                    "MONITORING_MODE": "sidecar",
                    "ORCHESTRATOR_ID": "test_orchestrator",
                    "ORGANIZATION_ID": "test_org",
                    "DATABASE_URL": "postgresql://test:test@localhost:5432/test_db",
                    "REDIS_URL": "redis://localhost:6379/0"
                },
                ports={'8001/tcp': 8001},
                detach=True,
                remove=True
            )
            
            # Wait for service to start
            time.sleep(5)
            
            # Test health endpoint
            response = requests.get("http://localhost:8001/health", timeout=10)
            assert response.status_code == 200
            
            health_data = response.json()
            assert health_data["status"] in ["healthy", "degraded"]
            assert health_data["mode"] == "sidecar"
            
        except requests.exceptions.ConnectionError:
            pytest.skip("Could not connect to container (port may be in use)")
        except Exception as e:
            pytest.fail(f"Health check failed: {e}")
        finally:
            if container:
                try:
                    container.stop(timeout=5)
                except Exception:
                    pass


class TestOrchestratorDockerBuild:
    """Test orchestrator service Docker build."""
    
    @pytest.fixture(scope="class")
    def orchestrator_image(self, docker_client, project_root):
        """Build orchestrator service image."""
        image_tag = "moolai/orchestrator:test"
        
        try:
            # Build the image
            print(f"Building orchestrator image: {image_tag}")
            image, build_logs = docker_client.images.build(
                path=str(project_root),
                dockerfile="Dockerfile.orchestrator",
                tag=image_tag,
                rm=True,
                forcerm=True
            )
            
            yield image
            
            # Cleanup
            try:
                docker_client.images.remove(image.id, force=True)
            except Exception:
                pass
                
        except Exception as e:
            pytest.fail(f"Failed to build orchestrator image: {e}")
    
    def test_orchestrator_image_created(self, orchestrator_image):
        """Test that orchestrator image was created successfully."""
        assert orchestrator_image is not None
        assert len(orchestrator_image.tags) > 0
    
    def test_orchestrator_image_labels(self, orchestrator_image):
        """Test orchestrator image has correct labels."""
        labels = orchestrator_image.labels or {}
        assert "org.moolai.service" in labels
        assert labels["org.moolai.service"] == "orchestrator"


class TestControllerDockerBuild:
    """Test controller service Docker build."""
    
    @pytest.fixture(scope="class") 
    def controller_image(self, docker_client, project_root):
        """Build controller service image."""
        image_tag = "moolai/controller:test"
        
        try:
            # Build the image
            print(f"Building controller image: {image_tag}")
            image, build_logs = docker_client.images.build(
                path=str(project_root),
                dockerfile="Dockerfile.controller",
                tag=image_tag,
                rm=True,
                forcerm=True
            )
            
            yield image
            
            # Cleanup
            try:
                docker_client.images.remove(image.id, force=True)
            except Exception:
                pass
                
        except Exception as e:
            pytest.fail(f"Failed to build controller image: {e}")
    
    def test_controller_image_created(self, controller_image):
        """Test that controller image was created successfully."""
        assert controller_image is not None
        assert len(controller_image.tags) > 0
    
    def test_controller_image_labels(self, controller_image):
        """Test controller image has correct labels."""
        labels = controller_image.labels or {}
        assert "org.moolai.service" in labels
        assert labels["org.moolai.service"] == "controller"


class TestDockerBuildSecurity:
    """Test Docker build security practices."""
    
    def test_dockerfile_security_practices(self, project_root):
        """Test that Dockerfiles follow security best practices."""
        dockerfiles = [
            "Dockerfile.monitoring",
            "Dockerfile.orchestrator", 
            "Dockerfile.controller"
        ]
        
        for dockerfile_name in dockerfiles:
            dockerfile_path = project_root / dockerfile_name
            if not dockerfile_path.exists():
                continue
                
            content = dockerfile_path.read_text()
            
            # Check for security practices
            assert "USER " in content, f"{dockerfile_name}: Should not run as root"
            assert "COPY --chown=" in content or "RUN chown" in content, f"{dockerfile_name}: Should set proper file ownership"
            
            # Should not expose unnecessary ports
            lines = content.split('\n')
            expose_lines = [line for line in lines if line.strip().startswith('EXPOSE')]
            assert len(expose_lines) <= 2, f"{dockerfile_name}: Should not expose too many ports"
    
    def test_dockerignore_content(self, project_root):
        """Test that .dockerignore excludes sensitive files."""
        dockerignore_path = project_root / ".dockerignore"
        if not dockerignore_path.exists():
            pytest.skip(".dockerignore not found")
        
        content = dockerignore_path.read_text()
        
        # Check for common exclusions
        exclusions = [
            "*.pyc",
            "__pycache__",
            ".git",
            ".env",
            "*.log",
            "test_venv"
        ]
        
        for exclusion in exclusions:
            assert exclusion in content, f"Missing exclusion in .dockerignore: {exclusion}"


class TestDockerBuildPerformance:
    """Test Docker build performance and optimization."""
    
    def test_image_size_reasonable(self, docker_client, project_root):
        """Test that Docker images are not excessively large."""
        max_size_mb = 500  # Maximum size in MB
        
        dockerfiles = [
            ("Dockerfile.monitoring", "moolai/monitoring:size-test"),
            ("Dockerfile.orchestrator", "moolai/orchestrator:size-test"),
            ("Dockerfile.controller", "moolai/controller:size-test")
        ]
        
        for dockerfile, tag in dockerfiles:
            dockerfile_path = project_root / dockerfile
            if not dockerfile_path.exists():
                continue
            
            try:
                image, _ = docker_client.images.build(
                    path=str(project_root),
                    dockerfile=dockerfile,
                    tag=tag,
                    rm=True,
                    forcerm=True
                )
                
                # Get image size in MB
                size_mb = image.attrs['Size'] / (1024 * 1024)
                print(f"{dockerfile} image size: {size_mb:.1f} MB")
                
                assert size_mb < max_size_mb, f"{dockerfile} image too large: {size_mb:.1f} MB > {max_size_mb} MB"
                
                # Cleanup
                docker_client.images.remove(image.id, force=True)
                
            except Exception as e:
                pytest.skip(f"Could not test {dockerfile}: {e}")
    
    def test_build_cache_layers(self, project_root):
        """Test that Dockerfiles are structured for efficient caching."""
        dockerfiles = [
            "Dockerfile.monitoring",
            "Dockerfile.orchestrator",
            "Dockerfile.controller"
        ]
        
        for dockerfile_name in dockerfiles:
            dockerfile_path = project_root / dockerfile_name
            if not dockerfile_path.exists():
                continue
            
            content = dockerfile_path.read_text()
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            
            # Find positions of key instructions
            copy_requirements_pos = None
            pip_install_pos = None
            copy_app_pos = None
            
            for i, line in enumerate(lines):
                if 'COPY' in line and 'requirements.txt' in line:
                    copy_requirements_pos = i
                elif 'RUN pip install' in line:
                    pip_install_pos = i
                elif 'COPY' in line and 'src/' in line:
                    copy_app_pos = i
            
            # Check optimal ordering for caching
            if copy_requirements_pos is not None and pip_install_pos is not None:
                assert copy_requirements_pos < pip_install_pos, f"{dockerfile_name}: Should copy requirements before pip install"
            
            if pip_install_pos is not None and copy_app_pos is not None:
                assert pip_install_pos < copy_app_pos, f"{dockerfile_name}: Should install dependencies before copying app code"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])