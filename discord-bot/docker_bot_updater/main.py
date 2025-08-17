import os
import shutil
import git
import docker
import time
import logging
import subprocess

# Config
git_url = 'https://github.com/kpreiksa/meshtastic-scripts.git'
TIME_DELAY = 5
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
    client = docker.from_env()
    try:
        # Build context should be the discord-bot directory (one level up from dockerfile_path)
        context_dir = './discord-bot'
        dockerfile_relative_path = 'bot_docker_files/Dockerfile'

        logging.info(f"🚧 Building image: {DOCKER_REG}/{DOCKER_IMAGE}:{version}")

        # Build the image with build output
        image, build_logs = client.images.build(
            path=context_dir,
            dockerfile=dockerfile_relative_path,
            tag=f"{DOCKER_REG}/{DOCKER_IMAGE}:{version}",
            rm=True,  # Remove intermediate containers
            forcerm=True  # Always remove intermediate containers
        )

        # Print build output
        for log in build_logs:
            if 'stream' in log:
                logging.info(log['stream'].strip())
            elif 'error' in log:
                logging.error(f"❌ Build error: {log['error']}")
                return False

        logging.info(f"✅ Build completed: {DOCKER_REG}/{DOCKER_IMAGE}:{version}")

        # Tag as latest
        image.tag(f"{DOCKER_REG}/{DOCKER_IMAGE}", "latest")

        # Test registry connection before pushing
        if not test_registry_connection_simple():
            logging.error("❌ Registry not accessible, skipping push")
            return False

        # Wait a moment for the registry to be ready
        time.sleep(5)

        # Try pushing with a simpler approach first
        if simple_push(f"{DOCKER_REG}/{DOCKER_IMAGE}:{version}"):
            logging.info(f"✅ Successfully pushed {DOCKER_REG}/{DOCKER_IMAGE}:{version}")
        else:
            logging.error(f"❌ Failed to push {DOCKER_REG}/{DOCKER_IMAGE}:{version}")
            return False

        # Push latest
        if simple_push(f"{DOCKER_REG}/{DOCKER_IMAGE}:latest"):
            logging.info(f"✅ Successfully pushed {DOCKER_REG}/{DOCKER_IMAGE}:latest")
        else:
            logging.error(f"❌ Failed to push {DOCKER_REG}/{DOCKER_IMAGE}:latest")
            return False

        logging.info(f"✅ Successfully built and pushed {DOCKER_REG}/{DOCKER_IMAGE}:{version} and latest")
        return True

    except Exception as e:
        logging.error(f"❌ Build/push failed: {str(e)}")
        return False
    finally:
        client.close()

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
