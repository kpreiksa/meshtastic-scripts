import os
import shutil
import git
import docker
import time
import logging
import subprocess

# Config
git_url = 'https://github.com/kpreiksa/meshtastic-scripts.git'
TIME_DELAY = 30
# Env Vars
DOCKER_REG = os.getenv("MY_DOCKER_REG")
DOCKER_IMAGE = 'meshtastic-discord-bot'
FORCE_REBUILD = os.getenv("FORCE_REBUILD", "false").lower() == "true"


log_file = 'meshtastic-docker-bot-updater.log'
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def main():
    print(f"Starting Meshtastic Discord Bot Updater")
    repo_path = '/tmp/meshtastic-scripts'
    # remove if it exists
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)
        logging.info(f"Removed existing repository at {repo_path}")

    # Test registry connection
    test_registry_connection()

    logging.info(f"Cloning repository from {git_url} to {repo_path}")
    repo = git.Repo.clone_from(git_url, '/tmp/meshtastic-scripts')
    os.chdir('/tmp/meshtastic-scripts')

    # First time checks
    version = check_bot_version_py()
    logging.info(f"Initial bot version: {version}")

    if not check_version_in_docker_reg(version) or FORCE_REBUILD:
        if FORCE_REBUILD:
            logging.info(f'Forced rebuild on startup requested')
        else:
            logging.info(f'Docker image not in registry, going to rebuild')
        build_and_push_docker_image(version)
    else:
        logging.info(f'Docker image {DOCKER_REG}/{DOCKER_IMAGE}:{version} is up to date')

    time.sleep(60*TIME_DELAY)
    while True:
        pulled = git_pull(repo)
        if pulled:
            logging.info("Changes detected, checking bot version...")
            version = check_bot_version_py()
            logging.info(f"Current bot version: {version}")
            if not check_version_in_docker_reg(version):
                logging.info(f"Version {version} is not in Docker registry. Building new image...")
                build_and_push_docker_image(version)
            else:
                logging.info(f"Version {version} is already in Docker registry.")
        else:
            logging.info(f"No changes detected. Waiting for next check. {TIME_DELAY} minutes")
        time.sleep(60*TIME_DELAY)

def test_registry_connection():
    """Test connection to the Docker registry"""
    import requests
    import time

    max_retries = 10
    retry_delay = 10

    for attempt in range(max_retries):
        try:
            logging.info(f"Testing registry connection (attempt {attempt + 1}/{max_retries})...")
            response = requests.get(f"http://{DOCKER_REG}/v2/", timeout=10)
            if response.status_code == 200:
                logging.info(f"✅ Registry connection successful: {DOCKER_REG}")
                return True
            else:
                logging.warning(f"⚠️ Registry returned status {response.status_code}")
        except Exception as e:
            logging.warning(f"⚠️ Registry connection failed: {e}")

        if attempt < max_retries - 1:
            logging.info(f"Waiting {retry_delay} seconds before retry...")
            time.sleep(retry_delay)

    logging.error(f"❌ Could not connect to registry after {max_retries} attempts")
    return False

def check_bot_version_py():
    """Read in the version from the version.py file"""
    version_file_path = './discord-bot/bot/version.py'
    with open(version_file_path) as f:
        exec(f.read())
    return locals().get("__version__")

def check_version_in_docker_reg(version):
    """Check if the version exists in the docker registry
    Input: version (str) - The version to check
    Output: bool - True if the version exists, False otherwise
    """
    client = docker.from_env()
    try:
        # First try to pull the image to check if it exists
        try:
            client.images.pull(f"{DOCKER_REG}/{DOCKER_IMAGE}:{version}")
            logging.info(f"✅ Found image in registry: {DOCKER_REG}/{DOCKER_IMAGE}:{version}")
            return True
        except docker.errors.ImageNotFound:
            logging.info(f"❌ Image not found in registry: {DOCKER_REG}/{DOCKER_IMAGE}:{version}")
            return False
        except Exception as e:
            logging.warning(f"⚠️ Could not check registry for {DOCKER_REG}/{DOCKER_IMAGE}:{version}: {e}")
            # If we can't connect to registry, assume image doesn't exist
            return False
    finally:
        client.close()

def git_pull(repo):
    """Pulls the latest for main branch from the repo
    Returns True if something changed
    """
    origin = repo.remotes.origin
    origin.fetch()
    if repo.head.commit != origin.refs.main.commit:
        repo.head.reset(origin.refs.main, index=True, working_tree=True)
        return True
    return False

def build_and_push_docker_image(version):
    """Builds and pushes the docker image for meshbot in meshtastic-scripts
    Dockerfile and configuration files are in ./discord-bot/bot_docker_files
    """
    # Test registry connection before building
    if not test_registry_connection_simple():
        logging.error("❌ Registry not accessible, skipping build")
        return False

    # Verify buildx is available
    try:
        result = subprocess.run(
            ["docker", "buildx", "version"],
            capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            logging.error("❌ Docker buildx not available")
            logging.error(f"STDERR: {result.stderr}")
            return False
        logging.info(f"✅ Docker buildx available: {result.stdout.strip()}")
    except Exception as e:
        logging.error(f"❌ Error checking buildx availability: {e}")
        return False

    # Create buildkitd configuration for insecure registry
    buildkitd_config = f'''
debug = true

insecure-entitlements = [ "network.host", "security.insecure"]

[registry."{DOCKER_REG}"]
  http = true
  insecure = true
'''

    config_dir = "/tmp/buildkit"
    config_file = f"{config_dir}/buildkitd.toml"
    try:
        os.makedirs(config_dir, exist_ok=True)
        with open(config_file, 'w') as f:
            f.write(buildkitd_config)
        logging.info(f"✅ Created buildkitd config for insecure registry: {config_file}")
    except Exception as e:
        logging.error(f"❌ Failed to create buildkitd config: {e}")
        return False

    # Setup buildx for multi-platform builds
    builder_name = "multiarch-builder"
    logging.info("🔧 Setting up buildx builder for multi-platform builds")
    logging.info("📋 Note: Insecure registry configuration should be done on the host Docker daemon")

    # Remove existing builder to ensure clean config
    try:
        subprocess.run(
            ["docker", "buildx", "rm", builder_name],
            capture_output=True, text=True, check=False
        )
        logging.info(f"🗑️ Removed existing builder: {builder_name}")
    except:
        pass

    # Create builder with buildkitd config
    try:
        logging.info(f"📦 Creating new buildx builder: {builder_name}")
        create_result = subprocess.run([
            "docker", "buildx", "create",
            "--name", builder_name,
            "--driver", "docker-container",
            f"--config", config_file,
            "--bootstrap"
        # ], capture_output=True, text=True, check=False)
        ], capture_output=True, text=True, check=False)

        if create_result.returncode != 0:
            logging.error(f"❌ Failed to create buildx builder:")
            logging.error(f"STDOUT: {create_result.stdout}")
            logging.error(f"STDERR: {create_result.stderr}")
            return False
        logging.info(f"✅ Successfully created buildx builder: {builder_name}")
        logging.info(f"STDOUT: {create_result.stdout}")
    except Exception as e:
        logging.error(f"❌ Exception during buildx builder setup: {e}")
        return False

    # Use the builder
    try:
        use_result = subprocess.run(
            ["docker", "buildx", "use", builder_name],
            capture_output=True, text=True, check=False
        )
        if use_result.returncode != 0:
            logging.error(f"❌ Failed to use buildx builder:")
            logging.error(f"STDOUT: {use_result.stdout}")
            logging.error(f"STDERR: {use_result.stderr}")
            return False
        logging.info(f"✅ Using buildx builder: {builder_name}")
    except Exception as e:
        logging.error(f"❌ Exception using buildx builder: {e}")
        return False

    # Fixed paths to match the actual directory structure
    context_dir = './discord-bot'
    dockerfile_path = './discord-bot/bot_docker_files/Dockerfile'

    logging.info(f"🚧 Building and pushing multi-platform image: {DOCKER_REG}/{DOCKER_IMAGE}:{version}")
    logging.info("🎯 Target platforms: linux/amd64, linux/arm64/v8")
    logging.info(f"🔒 Using insecure registry: {DOCKER_REG}")

    # Build and push multi-platform images using buildx
    command = [
        "docker", "buildx", "build",
        "--platform", "linux/amd64,linux/arm64/v8",
        "-f", dockerfile_path,
        "-t", f"{DOCKER_REG}/{DOCKER_IMAGE}:{version}",
        "-t", f"{DOCKER_REG}/{DOCKER_IMAGE}:latest",
        "--push",
        context_dir
    ]

    logging.info(f"Running buildx command: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode == 0:
        logging.info(f"✅ Successfully built and pushed multi-platform images:")
        logging.info(f"   - {DOCKER_REG}/{DOCKER_IMAGE}:{version}")
        logging.info(f"   - {DOCKER_REG}/{DOCKER_IMAGE}:latest")
        logging.info("📋 Supported platforms: linux/amd64, linux/arm64/v8")
        return True
    else:
        logging.error(f"❌ Multi-platform build and push failed:")
        logging.error(f"STDOUT: {result.stdout}")
        logging.error(f"STDERR: {result.stderr}")
        return False

def test_registry_connection_simple():
    """Simple registry connection test"""
    import requests
    try:
        response = requests.get(f"http://{DOCKER_REG}/v2/", timeout=30)
        return response.status_code == 200
    except:
        return False

def simple_push(image_tag):
    """Simple push using subprocess"""

    command = [
        "docker", "push", image_tag
    ]
    logging.info(f'Running docker push via subprocess')
    result = subprocess.run(command, capture_output=True, text=True)
    logging.info(f'Subprocess output: {result.stdout}')

    if result.returncode == 0:
        logging.info(f"📤 Push succeeded: {image_tag}")
        return True
    else:
        logging.warning(f"Push failed: {result.stderr}")
        return False

if __name__ == "__main__":
    main()
