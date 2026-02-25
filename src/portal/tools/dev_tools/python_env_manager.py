"""Python Environment Manager Tool"""

import os
import sys
import subprocess
from typing import Dict, Any, List

from portal.core.interfaces.tool import BaseTool, ToolMetadata, ToolParameter, ToolCategory


class PythonEnvManagerTool(BaseTool):
    """Manage Python virtual environments"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="python_env_manager",
            description="Create, manage, and inspect Python virtual environments",
            category=ToolCategory.DEV,
            version="1.0.0",
            requires_confirmation=True,
            parameters=[
                ToolParameter(
                    name="action",
                    param_type="string",
                    description="Action: create, list, install, info, freeze",
                    required=True
                ),
                ToolParameter(
                    name="env_path",
                    param_type="string",
                    description="Path to virtual environment",
                    required=False
                ),
                ToolParameter(
                    name="packages",
                    param_type="list",
                    description="List of packages to install",
                    required=False
                )
            ],
            examples=["Create venv at ./myenv"]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Manage Python environments"""
        try:
            action = parameters.get("action", "").lower()
            
            if action == "create":
                return await self._create_env(parameters.get("env_path", "venv"))
            elif action == "list":
                return await self._list_envs()
            elif action == "install":
                return await self._install_packages(
                    parameters.get("env_path", "venv"),
                    parameters.get("packages", [])
                )
            elif action == "info":
                return await self._env_info(parameters.get("env_path", "venv"))
            elif action == "freeze":
                return await self._freeze(parameters.get("env_path", "venv"))
            else:
                return self._error_response(f"Unknown action: {action}")
        
        except Exception as e:
            return self._error_response(str(e))
    
    async def _create_env(self, env_path: str) -> Dict[str, Any]:
        """Create a new virtual environment"""
        import venv
        
        if os.path.exists(env_path):
            return self._error_response(f"Environment already exists: {env_path}")
        
        venv.create(env_path, with_pip=True)
        
        return self._success_response({
            "message": f"Created virtual environment: {env_path}",
            "activate": f"source {env_path}/bin/activate"
        })
    
    async def _list_envs(self) -> Dict[str, Any]:
        """List virtual environments in current directory"""
        envs = []
        
        for item in os.listdir('.'):
            if os.path.isdir(item):
                # Check if it looks like a venv
                if os.path.exists(os.path.join(item, 'bin', 'python')) or \
                   os.path.exists(os.path.join(item, 'Scripts', 'python.exe')):
                    envs.append(item)
        
        return self._success_response({
            "environments": envs,
            "count": len(envs)
        })
    
    async def _install_packages(self, env_path: str, packages: List[str]) -> Dict[str, Any]:
        """Install packages in environment"""
        if not packages:
            return self._error_response("No packages specified")
        
        pip_path = os.path.join(env_path, 'bin', 'pip')
        if not os.path.exists(pip_path):
            pip_path = os.path.join(env_path, 'Scripts', 'pip.exe')
        
        if not os.path.exists(pip_path):
            return self._error_response(f"pip not found in environment: {env_path}")
        
        # Install packages
        result = subprocess.run(
            [pip_path, 'install'] + packages,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return self._success_response({
                "message": f"Installed {len(packages)} packages",
                "packages": packages,
                "output": result.stdout[:1000]
            })
        else:
            return self._error_response(f"Installation failed: {result.stderr[:500]}")
    
    async def _env_info(self, env_path: str) -> Dict[str, Any]:
        """Get environment information"""
        python_path = os.path.join(env_path, 'bin', 'python')
        if not os.path.exists(python_path):
            python_path = os.path.join(env_path, 'Scripts', 'python.exe')
        
        if not os.path.exists(python_path):
            return self._error_response(f"Environment not found: {env_path}")
        
        # Get Python version
        result = subprocess.run(
            [python_path, '--version'],
            capture_output=True,
            text=True
        )
        
        return self._success_response({
            "path": os.path.abspath(env_path),
            "python_version": result.stdout.strip(),
            "python_executable": python_path
        })
    
    async def _freeze(self, env_path: str) -> Dict[str, Any]:
        """Get installed packages"""
        pip_path = os.path.join(env_path, 'bin', 'pip')
        if not os.path.exists(pip_path):
            pip_path = os.path.join(env_path, 'Scripts', 'pip.exe')
        
        if not os.path.exists(pip_path):
            return self._error_response(f"Environment not found: {env_path}")
        
        result = subprocess.run(
            [pip_path, 'freeze'],
            capture_output=True,
            text=True
        )
        
        packages = result.stdout.strip().split('\n') if result.stdout else []
        
        return self._success_response({
            "packages": packages,
            "count": len(packages)
        })
