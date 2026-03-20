"""
그래프 관련 API 라우터
프로젝트 컨텍스트 메커니즘을 사용해 서버에서 상태를 영구 저장한다.
"""

import os
import traceback
import threading
from flask import request, jsonify

from . import graph_bp
from ..config import Config
from ..services.ontology_generator import OntologyGenerator
from ..services.graph_builder import GraphBuilderService
from ..services.text_processor import TextProcessor
from ..utils.file_parser import FileParser
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from ..models.task import TaskManager, TaskStatus
from ..models.project import ProjectManager, ProjectStatus

# 로거를 가져온다
logger = get_logger('mirofish.api')

_project_build_locks = {}
_project_build_locks_guard = threading.Lock()


def _build_lock_for(project_id: str) -> threading.Lock:
    with _project_build_locks_guard:
        if project_id not in _project_build_locks:
            _project_build_locks[project_id] = threading.Lock()
        return _project_build_locks[project_id]


def _coerce_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def allowed_file(filename: str) -> bool:
    """파일 확장자가 허용되는지 확인한다"""
    if not filename or '.' not in filename:
        return False
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    return ext in Config.ALLOWED_EXTENSIONS


# ============== 프로젝트 관리 인터페이스 ==============

@graph_bp.route('/project/<project_id>', methods=['GET'])
def get_project(project_id: str):
    """프로젝트 상세 정보를 가져온다"""
    project = ProjectManager.get_project(project_id)

    if not project:
        return jsonify({
            "success": False,
            "error": f"프로젝트가 존재하지 않음: {project_id}"
        }), 404

    return jsonify({
        "success": True,
        "data": project.to_dict()
    })


@graph_bp.route('/project/list', methods=['GET'])
def list_projects():
    """모든 프로젝트를 나열한다"""
    limit = request.args.get('limit', 50, type=int)
    projects = ProjectManager.list_projects(limit=limit)

    return jsonify({
        "success": True,
        "data": [p.to_dict() for p in projects],
        "count": len(projects)
    })


@graph_bp.route('/project/<project_id>', methods=['DELETE'])
def delete_project(project_id: str):
    """프로젝트를 삭제한다"""
    success = ProjectManager.delete_project(project_id)

    if not success:
        return jsonify({
            "success": False,
            "error": f"프로젝트가 존재하지 않거나 삭제에 실패함: {project_id}"
        }), 404

    return jsonify({
        "success": True,
        "message": f"프로젝트가 삭제됨: {project_id}"
    })


@graph_bp.route('/project/<project_id>/reset', methods=['POST'])
def reset_project(project_id: str):
    """프로젝트 상태를 초기화한다. (그래프를 다시 구성할 때 사용)"""
    project = ProjectManager.get_project(project_id)

    if not project:
        return jsonify({
            "success": False,
            "error": f"프로젝트가 존재하지 않음: {project_id}"
        }), 404

    # 온톨로지 생성 완료 상태로 초기화한다.
    if project.ontology:
        project.status = ProjectStatus.ONTOLOGY_GENERATED
    else:
        project.status = ProjectStatus.CREATED

    project.graph_id = None
    project.graph_build_task_id = None
    project.error = None
    ProjectManager.save_project(project)

    return jsonify({
        "success": True,
        "message": f"프로젝트가 초기화됨: {project_id}",
        "data": project.to_dict()
    })


# ============== 인터페이스 1: 파일 업로드 및 온톨로지 생성 ==============

@graph_bp.route('/ontology/generate', methods=['POST'])
def generate_ontology():
    """
    인터페이스 1: 파일을 업로드하고 분석해 온톨로지 정의를 생성한다.

    요청 방식: multipart/form-data

    파라미터:
        files: 업로드할 파일 (PDF/MD/TXT), 여러 개 가능
        simulation_requirement: 시뮬레이션 요구사항 설명 (필수)
        project_name: 프로젝트 이름 (선택)
        additional_context: 추가 설명 (선택)

    반환:
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "ontology": {
                    "entity_types": [...],
                    "edge_types": [...],
                    "analysis_summary": "..."
                },
                "files": [...],
                "total_text_length": 12345
            }
        }
    """
    try:
        logger.info("=== 온톨로지 정의 생성을 시작함 ===")

        # 파라미터를 가져온다.
        simulation_requirement = request.form.get('simulation_requirement', '')
        project_name = request.form.get('project_name', 'Unnamed Project')
        additional_context = request.form.get('additional_context', '')

        logger.debug(f"프로젝트 이름: {project_name}")
        logger.debug(f"시뮬레이션 요구사항: {simulation_requirement[:100]}...")

        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": "시뮬레이션 요구사항 설명을 제공해 주세요 (simulation_requirement)"
            }), 400

        # 업로드된 파일을 가져온다.
        uploaded_files = request.files.getlist('files')
        if not uploaded_files or all(not f.filename for f in uploaded_files):
            return jsonify({
                "success": False,
                "error": "문서 파일을 최소 하나 이상 업로드해 주세요"
            }), 400

        # 프로젝트를 생성한다.
        project = ProjectManager.create_project(name=project_name)
        project.simulation_requirement = simulation_requirement
        ProjectManager.save_project(project)
        logger.info(f"프로젝트 생성: {project.project_id}")

        # 파일을 저장한 뒤, 독립적인 텍스트 추출만 병렬 실행한다.
        saved_files = []

        for file in uploaded_files:
            if file and file.filename and allowed_file(file.filename):
                # 파일을 프로젝트 디렉터리에 저장한다.
                file_info = ProjectManager.save_file_to_project(
                    project.project_id,
                    file,
                    file.filename
                )
                project.files.append({
                    "filename": file_info["original_filename"],
                    "size": file_info["size"]
                })
                saved_files.append(file_info)

        file_paths = [file_info["path"] for file_info in saved_files]
        extracted_texts = FileParser.extract_texts_parallel(
            file_paths,
            max_workers=Config.FILE_EXTRACTION_PARALLEL_WORKERS,
        )

        document_texts = []
        all_text = ""
        for file_info, text in zip(saved_files, extracted_texts):
            text = TextProcessor.preprocess_text(text)
            document_texts.append(text)
            all_text += f"\n\n=== {file_info['original_filename']} ===\n{text}"

        if not document_texts:
            ProjectManager.delete_project(project.project_id)
            return jsonify({
                "success": False,
                "error": "성공적으로 처리된 문서가 없습니다. 파일 형식을 확인해 주세요"
            }), 400

        # 추출된 텍스트를 저장한다.
        project.total_text_length = len(all_text)
        ProjectManager.save_extracted_text(project.project_id, all_text)
        ProjectManager.save_project(project)
        logger.info(
            "텍스트 추출 완료, 총 %s자, 파일 %s개, 병렬 워커 %s",
            len(all_text),
            len(document_texts),
            min(Config.FILE_EXTRACTION_PARALLEL_WORKERS, len(file_paths)) if file_paths else 1,
        )

        # 온톨로지를 생성한다.
        logger.info("LLM을 호출해 온톨로지 정의를 생성하는 중...")
        generator = OntologyGenerator()
        ontology = generator.generate(
            document_texts=document_texts,
            simulation_requirement=simulation_requirement,
            additional_context=additional_context if additional_context else None
        )

        # 온톨로지를 프로젝트에 저장한다.
        entity_count = len(ontology.get("entity_types", []))
        edge_count = len(ontology.get("edge_types", []))
        logger.info(f"온톨로지 생성 완료: 엔티티 유형 {entity_count}개, 관계 유형 {edge_count}개")

        project.ontology = {
            "entity_types": ontology.get("entity_types", []),
            "edge_types": ontology.get("edge_types", [])
        }
        project.analysis_summary = ontology.get("analysis_summary", "")
        project.status = ProjectStatus.ONTOLOGY_GENERATED
        ProjectManager.save_project(project)
        logger.info(f"=== 온톨로지 생성 완료 === 프로젝트 ID: {project.project_id}")

        return jsonify({
            "success": True,
            "data": {
                "project_id": project.project_id,
                "project_name": project.name,
                "ontology": project.ontology,
                "analysis_summary": project.analysis_summary,
                "files": project.files,
                "total_text_length": project.total_text_length
            }
        })

    except Exception as e:
        logger.error("온톨로지 정의 생성 실패: %s", str(e))
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 인터페이스 2: 그래프 구성 ==============

@graph_bp.route('/build', methods=['POST'])
def build_graph():
    """
    인터페이스 2: project_id를 기준으로 그래프를 구성한다.

    요청(JSON):
        {
            "project_id": "proj_xxxx",  // 필수, 인터페이스 1에서 생성됨
            "graph_name": "그래프 이름",    // 선택
            "chunk_size": 500,          // 선택, 기본값 500
            "chunk_overlap": 50,        // 선택, 기본값 50
            "batch_size": 3,            // 선택, 기본값 Config.GRAPH_BUILD_BATCH_SIZE
            "parallel_workers": "auto"  // 선택, 기본값은 연결된 모델 서버 설정을 자동 감지
        }

    반환:
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "task_id": "task_xxxx",
                "message": "그래프 구성 작업이 시작됨"
            }
        }
    """
    try:
        logger.info("=== 그래프 구성을 시작함 ===")

        if not Config.LLM_API_KEY:
            logger.error("설정 오류: LLM_API_KEY가 설정되지 않음")
            return jsonify({
                "success": False,
                "error": "설정 오류: LLM_API_KEY가 설정되지 않음"
            }), 500

        # 요청을 파싱한다.
        data = request.get_json() or {}
        project_id = data.get('project_id')
        logger.debug(f"요청 파라미터: project_id={project_id}")

        if not project_id:
            return jsonify({
                "success": False,
                "error": "project_id를 제공해 주세요"
            }), 400

        force = _coerce_bool(data.get('force', False))  # 강제 재구성

        with _build_lock_for(project_id):
            # 프로젝트를 가져온다.
            project = ProjectManager.get_project(project_id)
            if not project:
                return jsonify({
                    "success": False,
                    "error": f"프로젝트가 존재하지 않음: {project_id}"
                }), 404

            # 프로젝트 상태를 확인한다.
            if project.status == ProjectStatus.CREATED:
                return jsonify({
                    "success": False,
                    "error": "프로젝트의 온톨로지가 아직 생성되지 않았습니다. 먼저 /ontology/generate를 호출해 주세요"
                }), 400

            if project.status == ProjectStatus.GRAPH_BUILDING and not force:
                return jsonify({
                    "success": False,
                    "error": "그래프가 이미 구성 중입니다. 중복 제출하지 마세요. 강제 재구성이 필요하면 force: true를 추가하세요",
                    "task_id": project.graph_build_task_id
                }), 400

            # 강제 재구성인 경우 상태를 초기화한다.
            if force and project.status in [ProjectStatus.GRAPH_BUILDING, ProjectStatus.FAILED, ProjectStatus.GRAPH_COMPLETED]:
                project.status = ProjectStatus.ONTOLOGY_GENERATED
                project.graph_id = None
                project.graph_build_task_id = None
                project.error = None

            # 설정을 가져온다.
            graph_name = data.get('graph_name', project.name or 'MiroFish Graph')
            chunk_size = data.get('chunk_size', project.chunk_size or Config.DEFAULT_CHUNK_SIZE)
            chunk_overlap = data.get('chunk_overlap', project.chunk_overlap or Config.DEFAULT_CHUNK_OVERLAP)
            batch_size = data.get('batch_size', Config.GRAPH_BUILD_BATCH_SIZE)
            raw_parallel_workers = data.get('parallel_workers')

            try:
                batch_size = max(1, int(batch_size))
            except (TypeError, ValueError):
                return jsonify({
                    "success": False,
                    "error": f"batch_size가 유효하지 않음: {batch_size}"
                }), 400

            if raw_parallel_workers is None or str(raw_parallel_workers).strip().lower() in {"", "auto"}:
                parallel_workers, parallel_source = LLMClient.get_recommended_parallel_requests_with_source(
                    fallback=Config.GRAPH_BUILD_PARALLEL_WORKERS,
                    max_cap=Config.GRAPH_BUILD_MAX_PARALLEL_WORKERS,
                )
            else:
                try:
                    parallel_workers = min(
                        max(1, int(raw_parallel_workers)),
                        Config.GRAPH_BUILD_MAX_PARALLEL_WORKERS,
                    )
                    parallel_source = "request_override"
                except (TypeError, ValueError):
                    return jsonify({
                        "success": False,
                        "error": f"parallel_workers가 유효하지 않음: {raw_parallel_workers}"
                    }), 400

            # 프로젝트 설정을 갱신한다.
            project.chunk_size = chunk_size
            project.chunk_overlap = chunk_overlap

            # 추출된 텍스트를 가져온다.
            text = ProjectManager.get_extracted_text(project_id)
            if not text:
                return jsonify({
                    "success": False,
                    "error": "추출된 텍스트 내용을 찾을 수 없음"
                }), 400

            # 온톨로지를 가져온다.
            ontology = project.ontology
            if not ontology:
                return jsonify({
                    "success": False,
                    "error": "온톨로지 정의를 찾을 수 없음"
                }), 400

            # 비동기 작업을 생성한다.
            task_manager = TaskManager()
            task_id = task_manager.create_task(f"그래프 구성: {graph_name}")
            logger.info(
                "그래프 구성 작업 생성: task_id=%s, project_id=%s, batch_size=%s, parallel_workers=%s, parallel_source=%s",
                task_id,
                project_id,
                batch_size,
                parallel_workers,
                parallel_source,
            )

            # 프로젝트 상태를 갱신한다.
            project.status = ProjectStatus.GRAPH_BUILDING
            project.graph_build_task_id = task_id
            ProjectManager.save_project(project)

        # 백그라운드 작업을 시작한다.
        def build_task():
            build_logger = get_logger('mirofish.build')
            try:
                build_logger.info(f"[{task_id}] 그래프 구성을 시작함...")
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    message="그래프 구성 서비스 초기화 중..."
                )

                # 그래프 구성 서비스를 생성한다.
                builder = GraphBuilderService()

                # 분할한다.
                task_manager.update_task(
                    task_id,
                    message="텍스트 분할 중...",
                    progress=5
                )
                chunks = TextProcessor.split_text(
                    text,
                    chunk_size=chunk_size,
                    overlap=chunk_overlap
                )
                total_chunks = len(chunks)

                # 그래프를 생성한다.
                task_manager.update_task(
                    task_id,
                    message="로컬 그래프 생성 중...",
                    progress=10
                )
                graph_id = builder.create_graph(name=graph_name)

                # 프로젝트의 graph_id를 갱신한다.
                project.graph_id = graph_id
                ProjectManager.save_project(project)

                # 온톨로지를 설정한다.
                task_manager.update_task(
                    task_id,
                    message="온톨로지 정의 설정 중...",
                    progress=15
                )
                builder.set_ontology(graph_id, ontology)

                # 텍스트를 추가한다. (progress_callback 시그니처는 (msg, progress_ratio))
                def add_progress_callback(msg, progress_ratio):
                    progress = 15 + int(progress_ratio * 40)  # 15% - 55%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )

                task_manager.update_task(
                    task_id,
                    message=f"{total_chunks}개 텍스트 블록 추가 시작... (batch_size={batch_size}, parallel_workers={parallel_workers})",
                    progress=15
                )

                episode_uuids = builder.add_text_batches(
                    graph_id,
                    chunks,
                    batch_size=batch_size,
                    progress_callback=add_progress_callback,
                    parallel_workers=parallel_workers,
                )

                # 로컬 추출이 완료될 때까지 기다린다. (각 episode의 processed 상태 확인)
                task_manager.update_task(
                    task_id,
                    message="로컬 추출 데이터 처리 대기 중...",
                    progress=55
                )

                def wait_progress_callback(msg, progress_ratio):
                    progress = 55 + int(progress_ratio * 35)  # 55% - 90%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )

                builder._wait_for_episodes(graph_id, episode_uuids, wait_progress_callback)

                # 그래프 데이터를 가져온다.
                task_manager.update_task(
                    task_id,
                    message="그래프 데이터 가져오는 중...",
                    progress=95
                )
                graph_data = builder.get_graph_data(graph_id)

                # 프로젝트 상태를 갱신한다.
                project.status = ProjectStatus.GRAPH_COMPLETED
                ProjectManager.save_project(project)

                node_count = graph_data.get("node_count", 0)
                edge_count = graph_data.get("edge_count", 0)
                build_logger.info(f"[{task_id}] 그래프 구성 완료: graph_id={graph_id}, 노드={node_count}, 엣지={edge_count}")

                # 완료 처리
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.COMPLETED,
                    message="그래프 구성 완료",
                    progress=100,
                    result={
                        "project_id": project_id,
                        "graph_id": graph_id,
                        "node_count": node_count,
                        "edge_count": edge_count,
                        "chunk_count": total_chunks,
                        "batch_size": batch_size,
                        "parallel_workers": parallel_workers,
                        "parallel_source": parallel_source,
                    }
                )

            except Exception as e:
                # 프로젝트 상태를 실패로 갱신한다.
                build_logger.error(f"[{task_id}] 그래프 구성 실패: {str(e)}")
                build_logger.debug(traceback.format_exc())

                project.status = ProjectStatus.FAILED
                project.error = str(e)
                ProjectManager.save_project(project)

                task_manager.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    message=f"구성 실패: {str(e)}",
                    error=traceback.format_exc()
                )

        # 백그라운드 스레드를 시작한다.
        thread = threading.Thread(target=build_task, daemon=True)
        thread.start()

        return jsonify({
            "success": True,
            "data": {
                "project_id": project_id,
                "task_id": task_id,
                "message": "그래프 구성 작업이 시작되었습니다. /task/{task_id}로 진행 상황을 확인하세요"
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 작업 조회 인터페이스 ==============

@graph_bp.route('/task/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """작업 상태를 조회한다"""
    task = TaskManager().get_task(task_id)

    if not task:
        return jsonify({
            "success": False,
            "error": f"작업이 존재하지 않음: {task_id}"
        }), 404

    return jsonify({
        "success": True,
        "data": task.to_dict()
    })


@graph_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """모든 작업을 나열한다"""
    tasks = TaskManager().list_tasks()

    return jsonify({
        "success": True,
        "data": [t.to_dict() for t in tasks],
        "count": len(tasks)
    })


# ============== 그래프 데이터 인터페이스 ==============

@graph_bp.route('/data/<graph_id>', methods=['GET'])
def get_graph_data(graph_id: str):
    """그래프 데이터(노드와 엣지)를 가져온다"""
    try:
        builder = GraphBuilderService()
        graph_data = builder.get_graph_data(graph_id)

        return jsonify({
            "success": True,
            "data": graph_data
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@graph_bp.route('/dedupe/<graph_id>', methods=['POST'])
def dedupe_graph(graph_id: str):
    """기존 그래프의 다국어/이명 중복 엔티티를 병합한다."""
    try:
        data = request.get_json(silent=True) or {}
        dry_run = _coerce_bool(data.get("dry_run", True), default=True)
        include_graph_data = _coerce_bool(data.get("include_graph_data", False))

        builder = GraphBuilderService()
        result = builder.dedupe_graph_entities(graph_id, dry_run=dry_run)

        payload = {"result": result}
        if include_graph_data and not result.get("dry_run"):
            payload["graph"] = builder.get_graph_data(graph_id)

        return jsonify({
            "success": True,
            "data": payload,
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@graph_bp.route('/delete/<graph_id>', methods=['DELETE'])
def delete_graph(graph_id: str):
    """로컬 그래프를 삭제한다"""
    try:
        builder = GraphBuilderService()
        builder.delete_graph(graph_id)

        return jsonify({
            "success": True,
            "message": f"그래프가 삭제됨: {graph_id}"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
