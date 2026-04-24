import unittest
import docker
import os

class TestDockerNetwork(unittest.TestCase):
    def setUp(self):
        try:
            self.client = docker.from_env()
        except Exception as e:
            self.skipTest(f"Docker is not available: {e}")

    def test_list_networks(self):
        print("\n[Test] Current Docker Networks:")
        networks = self.client.networks.list()
        found_target = False
        target_name = os.environ.get("DOCKER_NETWORK", "ems_default")
        
        for net in networks:
            print(f" - Name: {net.name} (ID: {net.id[:12]})")
            if net.name == target_name:
                found_target = True
            elif target_name in net.name:
                print(f"   >>> Potential Match Found: {net.name}")

        if not found_target:
            print(f"\n[Warning] Network '{target_name}' NOT found in literal name.")
            print("This happens because Docker Compose prefixes the network name with the project name.")
        else:
            print(f"\n[Success] Network '{target_name}' found.")

    def test_container_start_with_network(self):
        """실제로 컨테이너를 생성하여 네트워크 연결을 테스트합니다."""
        target_name = os.environ.get("DOCKER_NETWORK", "ems_default")
        image = "alpine:latest"
        container_name = "test-network-check"
        
        # 기존 컨테이너 제거
        try:
            old = self.client.containers.get(container_name)
            old.remove(force=True)
        except:
            pass

        print(f"\n[Test] Attempting to start container '{container_name}' with network '{target_name}'")
        try:
            # 이미지 확보
            try:
                self.client.images.get(image)
            except:
                print(f"Pulling {image}...")
                self.client.images.pull(image)

            container = self.client.containers.create(
                image,
                name=container_name,
                network=target_name,
                command="sleep 10"
            )
            container.start()
            print(f"[Success] Container started successfully with network '{target_name}'")
            container.remove(force=True)
        except Exception as e:
            print(f"[Failure] Failed to start container: {e}")
            self.fail(f"Could not start container with network '{target_name}'")

if __name__ == "__main__":
    unittest.main()
