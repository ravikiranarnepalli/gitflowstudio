import requests
import sys
import json
from datetime import datetime

class GitSourceControlTester:
    def __init__(self, base_url="https://git-flow-master.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_repo_id = None
        self.test_config_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, list):
                        print(f"   Response: {len(response_data)} items")
                    elif isinstance(response_data, dict):
                        print(f"   Response keys: {list(response_data.keys())}")
                except:
                    print(f"   Response: {response.text[:100]}...")
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text}")

            return success, response.json() if response.content else {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_repositories(self):
        """Test repository CRUD operations"""
        print("\n" + "="*50)
        print("TESTING REPOSITORY OPERATIONS")
        print("="*50)

        # Test GET repositories (empty initially)
        success, repos = self.run_test(
            "Get Repositories (Empty)",
            "GET",
            "repos",
            200
        )

        # Test CREATE repository
        test_repo_data = {
            "name": "test-repo",
            "provider": "github",
            "url": "https://github.com/test/repo.git",
            "auth_type": "pat",
            "auth_data": {"token": "test_token_123"},
            "default_branch": "main",
            "is_local": False
        }

        success, repo_response = self.run_test(
            "Create Repository",
            "POST",
            "repos",
            200,
            data=test_repo_data
        )

        if success and 'id' in repo_response:
            self.test_repo_id = repo_response['id']
            print(f"   Created repo with ID: {self.test_repo_id}")

        # Test GET repositories (should have 1 now)
        success, repos = self.run_test(
            "Get Repositories (With Data)",
            "GET",
            "repos",
            200
        )

        # Test GET single repository
        if self.test_repo_id:
            success, repo = self.run_test(
                "Get Single Repository",
                "GET",
                f"repos/{self.test_repo_id}",
                200
            )

        # Test CREATE local repository
        local_repo_data = {
            "name": "local-app",
            "provider": "github",
            "url": "https://github.com/local/app.git",
            "auth_type": "pat",
            "auth_data": {"token": "local_token"},
            "default_branch": "main",
            "is_local": True
        }

        success, local_repo = self.run_test(
            "Create Local Repository",
            "POST",
            "repos",
            200,
            data=local_repo_data
        )

    def test_git_operations(self):
        """Test Git operations"""
        print("\n" + "="*50)
        print("TESTING GIT OPERATIONS")
        print("="*50)

        if not self.test_repo_id:
            print("❌ Skipping Git operations - no test repository available")
            return

        # Test CREATE BRANCH
        branch_data = {
            "branch_name": "feature/test-branch",
            "base_branch": "main"
        }

        success, branch_response = self.run_test(
            "Create Branch",
            "POST",
            f"repos/{self.test_repo_id}/create-branch",
            200,
            data=branch_data
        )

        # Test PUSH to branch
        push_data = {
            "branch_name": "feature/test-branch",
            "commit_message": "Test commit message"
        }

        success, push_response = self.run_test(
            "Push to Branch",
            "POST",
            f"repos/{self.test_repo_id}/push",
            200,
            data=push_data
        )

        # Test MERGE branches
        merge_data = {
            "source_branch": "feature/test-branch",
            "target_branch": "main"
        }

        success, merge_response = self.run_test(
            "Merge Branches",
            "POST",
            f"repos/{self.test_repo_id}/merge",
            200,
            data=merge_data
        )

    def test_operations_log(self):
        """Test operations logging"""
        print("\n" + "="*50)
        print("TESTING OPERATIONS LOG")
        print("="*50)

        # Test GET all operations
        success, operations = self.run_test(
            "Get All Operations",
            "GET",
            "operations",
            200
        )

        # Test GET operations for specific repo
        if self.test_repo_id:
            success, repo_operations = self.run_test(
                "Get Repository Operations",
                "GET",
                "operations",
                200,
                params={"repo_id": self.test_repo_id}
            )

        # Test CREATE operation manually
        operation_data = {
            "repo_id": self.test_repo_id or "test-repo-id",
            "operation_type": "test_operation",
            "branch_name": "test-branch",
            "status": "success",
            "message": "Test operation created manually"
        }

        success, operation = self.run_test(
            "Create Operation Log",
            "POST",
            "operations",
            200,
            data=operation_data
        )

    def test_deployment_configs(self):
        """Test deployment configuration"""
        print("\n" + "="*50)
        print("TESTING DEPLOYMENT CONFIGURATIONS")
        print("="*50)

        # Test GET deployment configs (empty initially)
        success, configs = self.run_test(
            "Get Deployment Configs (Empty)",
            "GET",
            "deployment-configs",
            200
        )

        # Test CREATE FTP deployment config
        if self.test_repo_id:
            ftp_config_data = {
                "repo_id": self.test_repo_id,
                "deploy_type": "ftp",
                "config": {
                    "host": "ftp.example.com",
                    "username": "testuser",
                    "password": "testpass",
                    "path": "/public_html",
                    "use_tls": True
                }
            }

            success, config_response = self.run_test(
                "Create FTP Deployment Config",
                "POST",
                "deployment-configs",
                200,
                data=ftp_config_data
            )

            if success and 'id' in config_response:
                self.test_config_id = config_response['id']

        # Test CREATE cPanel deployment config
        if self.test_repo_id:
            cpanel_config_data = {
                "repo_id": self.test_repo_id,
                "deploy_type": "cpanel",
                "config": {
                    "host": "cpanel.example.com",
                    "username": "cpaneluser",
                    "api_token": "test_api_token_123"
                }
            }

            success, cpanel_config = self.run_test(
                "Create cPanel Deployment Config",
                "POST",
                "deployment-configs",
                200,
                data=cpanel_config_data
            )

        # Test GET deployment configs (should have data now)
        success, configs = self.run_test(
            "Get Deployment Configs (With Data)",
            "GET",
            "deployment-configs",
            200
        )

        # Test GET deployment configs for specific repo
        if self.test_repo_id:
            success, repo_configs = self.run_test(
                "Get Repository Deployment Configs",
                "GET",
                "deployment-configs",
                200,
                params={"repo_id": self.test_repo_id}
            )

    def test_deployment_operations(self):
        """Test deployment operations"""
        print("\n" + "="*50)
        print("TESTING DEPLOYMENT OPERATIONS")
        print("="*50)

        if not self.test_repo_id:
            print("❌ Skipping deployment operations - no test repository available")
            return

        # Test DEPLOY (this will likely fail due to invalid credentials, but should test the endpoint)
        deploy_data = {
            "branch_name": "main"
        }

        success, deploy_response = self.run_test(
            "Deploy Repository",
            "POST",
            f"repos/{self.test_repo_id}/deploy",
            200,  # Expecting 200 even if deployment fails
            data=deploy_data
        )

    def test_cleanup(self):
        """Clean up test data"""
        print("\n" + "="*50)
        print("CLEANING UP TEST DATA")
        print("="*50)

        # Delete deployment config
        if self.test_config_id:
            success, _ = self.run_test(
                "Delete Deployment Config",
                "DELETE",
                f"deployment-configs/{self.test_config_id}",
                200
            )

        # Delete repository
        if self.test_repo_id:
            success, _ = self.run_test(
                "Delete Repository",
                "DELETE",
                f"repos/{self.test_repo_id}",
                200
            )

def main():
    print("🚀 Starting Git Source Control API Tests")
    print(f"⏰ Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tester = GitSourceControlTester()

    # Run all test suites
    tester.test_repositories()
    tester.test_git_operations()
    tester.test_operations_log()
    tester.test_deployment_configs()
    tester.test_deployment_operations()
    tester.test_cleanup()

    # Print final results
    print("\n" + "="*60)
    print("📊 FINAL TEST RESULTS")
    print("="*60)
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Tests Failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed / tester.tests_run * 100):.1f}%")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())