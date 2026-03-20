"""
프로젝트 컨텍스트 관리
서버에서 프로젝트 상태를 영구 저장해 프런트엔드가 인터페이스 간에 대량의 데이터를 전달하지 않도록 한다.
"""

import os
import json
import uuid
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field, asdict
from ..config import Config
from ..utils.ontology import normalize_ontology


class ProjectStatus(str, Enum):
    """프로젝트 상태"""
    CREATED = "created"              # 생성 직후, 파일 업로드 완료
    ONTOLOGY_GENERATED = "ontology_generated"  # 온톨로지 생성 완료
    GRAPH_BUILDING = "graph_building"    # 그래프 구성 중
    GRAPH_COMPLETED = "graph_completed"  # 그래프 구성 완료
    FAILED = "failed"                # 실패


@dataclass
class Project:
    """프로젝트 데이터 모델"""
    project_id: str
    name: str
    status: ProjectStatus
    created_at: str
    updated_at: str
    
    # 파일 정보
    files: List[Dict[str, str]] = field(default_factory=list)  # [{filename, path, size}]
    total_text_length: int = 0
    
    # 온톨로지 정보 (인터페이스 1 생성 후 채움)
    ontology: Optional[Dict[str, Any]] = None
    analysis_summary: Optional[str] = None
    
    # 그래프 정보 (인터페이스 2 완료 후 채움)
    graph_id: Optional[str] = None
    graph_build_task_id: Optional[str] = None
    
    # 설정
    simulation_requirement: Optional[str] = None
    chunk_size: int = 500
    chunk_overlap: int = 50
    
    # 오류 정보
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환한다"""
        ontology = normalize_ontology(self.ontology) if self.ontology is not None else None
        return {
            "project_id": self.project_id,
            "name": self.name,
            "status": self.status.value if isinstance(self.status, ProjectStatus) else self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "files": self.files,
            "total_text_length": self.total_text_length,
            "ontology": ontology,
            "analysis_summary": self.analysis_summary,
            "graph_id": self.graph_id,
            "graph_build_task_id": self.graph_build_task_id,
            "simulation_requirement": self.simulation_requirement,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "error": self.error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """딕셔너리에서 생성한다"""
        status = data.get('status', 'created')
        if isinstance(status, str):
            status = ProjectStatus(status)

        raw_ontology = data.get('ontology')
        
        return cls(
            project_id=data['project_id'],
            name=data.get('name', 'Unnamed Project'),
            status=status,
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            files=data.get('files', []),
            total_text_length=data.get('total_text_length', 0),
            ontology=normalize_ontology(raw_ontology) if raw_ontology is not None else None,
            analysis_summary=data.get('analysis_summary'),
            graph_id=data.get('graph_id'),
            graph_build_task_id=data.get('graph_build_task_id'),
            simulation_requirement=data.get('simulation_requirement'),
            chunk_size=data.get('chunk_size', 500),
            chunk_overlap=data.get('chunk_overlap', 50),
            error=data.get('error')
        )


class ProjectManager:
    """프로젝트 관리자 - 프로젝트의 영구 저장과 조회를 담당한다"""
    
    # 프로젝트 저장 루트 디렉터리
    PROJECTS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'projects')
    
    @classmethod
    def _ensure_projects_dir(cls):
        """프로젝트 디렉터리가 존재하는지 확인한다"""
        os.makedirs(cls.PROJECTS_DIR, exist_ok=True)
    
    @classmethod
    def _get_project_dir(cls, project_id: str) -> str:
        """프로젝트 디렉터리 경로를 가져온다"""
        return os.path.join(cls.PROJECTS_DIR, project_id)
    
    @classmethod
    def _get_project_meta_path(cls, project_id: str) -> str:
        """프로젝트 메타데이터 파일 경로를 가져온다"""
        return os.path.join(cls._get_project_dir(project_id), 'project.json')
    
    @classmethod
    def _get_project_files_dir(cls, project_id: str) -> str:
        """프로젝트 파일 저장 디렉터리를 가져온다"""
        return os.path.join(cls._get_project_dir(project_id), 'files')
    
    @classmethod
    def _get_project_text_path(cls, project_id: str) -> str:
        """프로젝트 추출 텍스트 저장 경로를 가져온다"""
        return os.path.join(cls._get_project_dir(project_id), 'extracted_text.txt')
    
    @classmethod
    def create_project(cls, name: str = "Unnamed Project") -> Project:
        """
        새 프로젝트를 생성한다.
        
        Args:
            name: 프로젝트 이름
            
        Returns:
            새로 생성된 Project 객체
        """
        cls._ensure_projects_dir()
        
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        
        project = Project(
            project_id=project_id,
            name=name,
            status=ProjectStatus.CREATED,
            created_at=now,
            updated_at=now
        )
        
        # 프로젝트 디렉터리 구조를 생성한다.
        project_dir = cls._get_project_dir(project_id)
        files_dir = cls._get_project_files_dir(project_id)
        os.makedirs(project_dir, exist_ok=True)
        os.makedirs(files_dir, exist_ok=True)
        
        # 프로젝트 메타데이터를 저장한다.
        cls.save_project(project)
        
        return project
    
    @classmethod
    def save_project(cls, project: Project) -> None:
        """프로젝트 메타데이터를 저장한다"""
        project.updated_at = datetime.now().isoformat()
        if project.ontology is not None:
            project.ontology = normalize_ontology(project.ontology)
        meta_path = cls._get_project_meta_path(project.project_id)
        
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(project.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def get_project(cls, project_id: str) -> Optional[Project]:
        """
        프로젝트를 가져온다.
        
        Args:
            project_id: 프로젝트 ID
            
        Returns:
            Project 객체, 없으면 None
        """
        meta_path = cls._get_project_meta_path(project_id)
        
        if not os.path.exists(meta_path):
            return None
        
        with open(meta_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return Project.from_dict(data)
    
    @classmethod
    def list_projects(cls, limit: int = 50) -> List[Project]:
        """
        모든 프로젝트를 나열한다.
        
        Args:
            limit: 반환 개수 제한
            
        Returns:
            생성 시간 내림차순의 프로젝트 목록
        """
        cls._ensure_projects_dir()
        
        projects = []
        for project_id in os.listdir(cls.PROJECTS_DIR):
            project = cls.get_project(project_id)
            if project:
                projects.append(project)
        
        # 생성 시간 기준 내림차순 정렬
        projects.sort(key=lambda p: p.created_at, reverse=True)
        
        return projects[:limit]
    
    @classmethod
    def delete_project(cls, project_id: str) -> bool:
        """
        프로젝트와 모든 파일을 삭제한다.
        
        Args:
            project_id: 프로젝트 ID
            
        Returns:
            삭제 성공 여부
        """
        project_dir = cls._get_project_dir(project_id)
        project = cls.get_project(project_id)
        
        if not os.path.exists(project_dir):
            return False
        
        if project and project.graph_id:
            graph_dir = os.path.join(Config.LOCAL_GRAPH_FOLDER, project.graph_id)
            if os.path.exists(graph_dir):
                shutil.rmtree(graph_dir)

        shutil.rmtree(project_dir)
        return True
    
    @classmethod
    def save_file_to_project(cls, project_id: str, file_storage, original_filename: str) -> Dict[str, str]:
        """
        업로드된 파일을 프로젝트 디렉터리에 저장한다.
        
        Args:
            project_id: 프로젝트 ID
            file_storage: Flask의 FileStorage 객체
            original_filename: 원본 파일명
            
        Returns:
            파일 정보 딕셔너리 {filename, path, size}
        """
        files_dir = cls._get_project_files_dir(project_id)
        os.makedirs(files_dir, exist_ok=True)
        
        # 안전한 파일명을 생성한다.
        ext = os.path.splitext(original_filename)[1].lower()
        safe_filename = f"{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(files_dir, safe_filename)
        
        # 파일을 저장한다.
        file_storage.save(file_path)
        
        # 파일 크기를 가져온다.
        file_size = os.path.getsize(file_path)
        
        return {
            "original_filename": original_filename,
            "saved_filename": safe_filename,
            "path": file_path,
            "size": file_size
        }
    
    @classmethod
    def save_extracted_text(cls, project_id: str, text: str) -> None:
        """추출한 텍스트를 저장한다"""
        text_path = cls._get_project_text_path(project_id)
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text)
    
    @classmethod
    def get_extracted_text(cls, project_id: str) -> Optional[str]:
        """추출한 텍스트를 가져온다"""
        text_path = cls._get_project_text_path(project_id)
        
        if not os.path.exists(text_path):
            return None
        
        with open(text_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    @classmethod
    def get_project_files(cls, project_id: str) -> List[str]:
        """프로젝트의 모든 파일 경로를 가져온다"""
        files_dir = cls._get_project_files_dir(project_id)
        
        if not os.path.exists(files_dir):
            return []
        
        return [
            os.path.join(files_dir, f) 
            for f in os.listdir(files_dir) 
            if os.path.isfile(os.path.join(files_dir, f))
        ]
