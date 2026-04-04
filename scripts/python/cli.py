from __future__ import annotations

import re
import sys
from pathlib import Path

from .common import CommandError, die
from .context import export_context, verify_traceability
from .imported_skills import run_imported_skill, sync_imported_skills
from .qa import agent_verify, analyze_bsl, check_agent_docs, check_overlay_manifest, check_skill_bindings, codex_onboard, format_bsl
from .runtime import run_doctor, run_load_diff_src, run_load_task_src, run_profile_capability, run_tdd_xunit, task_trailers_render, task_trailers_select_commits, task_trailers_validate_message
from .template_tools import (
    bootstrap_post_copy,
    bootstrap_post_update,
    check_update,
    migrate_runtime_profile_v2,
    new_project,
    resolve_project_template,
    update_project,
    update_template,
)


CAPABILITY_LABELS = {
    "create-ib": "Create infobase",
    "dump-src": "Dump source tree",
    "load-src": "Load source tree",
    "update-db": "Update DB configuration",
    "diff-src": "Diff source tree",
    "run-xunit": "Run xUnit checks",
    "run-bdd": "Run BDD checks",
    "run-smoke": "Run smoke checks",
    "publish-http": "Publish HTTP service",
}


def _print_usage() -> None:
    print("Usage: python -m scripts.python.cli <command> [args...]")


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args or args[0] in {"-h", "--help"}:
        _print_usage()
        return 0
    command = args.pop(0)
    try:
        if command in CAPABILITY_LABELS:
            return run_profile_capability(command, CAPABILITY_LABELS[command], args).exit_code
        if command == "doctor":
            return run_doctor(args)
        if command == "load-diff-src":
            return run_load_diff_src(args)
        if command == "load-task-src":
            return run_load_task_src(args)
        if command == "tdd-xunit":
            return run_tdd_xunit(args)
        if command == "export-context":
            mode = args[0] if args else "--help"
            return export_context(mode)
        if command == "verify-traceability":
            return verify_traceability()
        if command == "agent-verify":
            return agent_verify()
        if command == "check-agent-docs":
            return check_agent_docs()
        if command == "check-skill-bindings":
            return check_skill_bindings()
        if command == "check-overlay-manifest":
            return check_overlay_manifest()
        if command == "codex-onboard":
            print(codex_onboard(), end="")
            return 0
        if command == "imported-skill":
            if not args:
                die("Usage: imported-skill <skill-name> [args...]")
            skill_name = args.pop(0)
            return run_imported_skill(skill_name, args)
        if command == "sync-imported-skills":
            source = ""
            index = 0
            while index < len(args):
                arg = args[index]
                if arg in {"-h", "--help"}:
                    print("Usage: sync-imported-skills --source /path/to/cc-1c-skills")
                    return 0
                if arg in {"-s", "--source"}:
                    index += 1
                    source = args[index]
                elif arg.startswith("--source="):
                    source = arg.split("=", 1)[1]
                else:
                    die(f"unknown option: {arg}")
                index += 1
            if not source:
                die("sync-imported-skills requires --source")
            return sync_imported_skills(Path(source))
        if command == "analyze-bsl":
            return analyze_bsl()
        if command == "format-bsl":
            return format_bsl()
        if command == "task-trailers-render":
            bead = ""
            work_item = ""
            index = 0
            while index < len(args):
                if args[index] == "--bead":
                    index += 1
                    bead = args[index]
                elif args[index] == "--work-item":
                    index += 1
                    work_item = args[index]
                else:
                    die(f"unknown argument for render: {args[index]}")
                index += 1
            print(task_trailers_render(bead, work_item), end="")
            return 0
        if command == "task-trailers-validate":
            message_file = None
            require_any = False
            index = 0
            while index < len(args):
                if args[index] == "--file":
                    index += 1
                    message_file = Path(args[index])
                elif args[index] == "--require-any":
                    require_any = True
                else:
                    die(f"unknown argument for validate-message: {args[index]}")
                index += 1
            if message_file is None:
                die("validate-message requires --file")
            task_trailers_validate_message(message_file, require_any=require_any)
            return 0
        if command == "task-trailers-select":
            repo = None
            selector_mode = ""
            selector_value = ""
            index = 0
            while index < len(args):
                if args[index] == "--repo":
                    index += 1
                    repo = Path(args[index])
                elif args[index] in {"--bead", "--work-item", "--range"}:
                    selector_mode = args[index][2:]
                    index += 1
                    selector_value = args[index]
                else:
                    die(f"unknown argument for select-commits: {args[index]}")
                index += 1
            for line in task_trailers_select_commits(selector_mode, selector_value, repo):
                print(line)
            return 0
        if command == "copier-post-copy":
            if len(args) != 9:
                die("copier-post-copy expects 9 arguments")
            return bootstrap_post_copy(*args)
        if command == "copier-post-update":
            if len(args) != 5:
                die("copier-post-update expects 5 arguments")
            return bootstrap_post_update(*args)
        if command == "check-update":
            requested_ref = ""
            index = 0
            while index < len(args):
                if args[index] in {"-r", "--vcs-ref"}:
                    index += 1
                    requested_ref = args[index]
                elif args[index].startswith("--vcs-ref="):
                    requested_ref = args[index].split("=", 1)[1]
                else:
                    die(f"unknown option: {args[index]}")
                index += 1
            return check_update(requested_ref)
        if command == "update-template":
            requested_ref = ""
            pretend = False
            index = 0
            while index < len(args):
                if args[index] in {"-r", "--vcs-ref"}:
                    index += 1
                    requested_ref = args[index]
                elif args[index].startswith("--vcs-ref="):
                    requested_ref = args[index].split("=", 1)[1]
                elif args[index] == "--pretend":
                    pretend = True
                else:
                    die(f"unknown option: {args[index]}")
                index += 1
            return update_template(requested_ref, pretend)
        if command == "migrate-runtime-profile-v2":
            if len(args) != 1:
                die("Usage: migrate-runtime-profile-v2 <legacy-profile.json>")
            print(migrate_runtime_profile_v2(Path(args[0])), end="")
            return 0
        if command == "new-project":
            destination = "."
            template = ""
            project_name = ""
            project_slug = ""
            preferred_adapter = ""
            openspec_tools = ""
            beads_prefix = ""
            use_defaults = False
            use_force = False
            init_git_repository = True
            init_beads = True
            index = 0
            while index < len(args):
                arg = args[index]
                if arg in {"-h", "--help"}:
                    print("Usage: new-project [destination] [options]")
                    return 0
                if arg in {"-t", "--template", "--project-name", "--slug", "--adapter", "--tools", "--beads-prefix"}:
                    if index + 1 >= len(args):
                        die(f"{arg} requires a value")
                    value = args[index + 1]
                    if arg in {"-t", "--template"}:
                        template = value
                    elif arg == "--project-name":
                        project_name = value
                    elif arg == "--slug":
                        project_slug = value
                    elif arg == "--adapter":
                        preferred_adapter = value
                    elif arg == "--tools":
                        openspec_tools = value
                    else:
                        beads_prefix = value
                    index += 2
                    continue
                if arg == "--defaults":
                    use_defaults = True
                elif arg == "--force":
                    use_force = True
                elif arg == "--no-git":
                    init_git_repository = False
                elif arg == "--no-beads":
                    init_beads = False
                elif arg.startswith("-"):
                    die(f"unknown option: {arg}")
                elif destination == ".":
                    destination = arg
                else:
                    die(f"unexpected positional argument: {arg}")
                index += 1
            default_name_source = Path.cwd() if destination in {".", "./"} else Path(destination)
            if not project_slug:
                project_slug = re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", default_name_source.name.lower())).strip("-")
            if not project_name:
                project_name = re.sub(r"[-_]+", " ", default_name_source.name)
            copier_args: list[str] = []
            if use_defaults:
                copier_args.append("--defaults")
            if use_force:
                copier_args.append("--force")
            if project_name:
                copier_args.extend(["-d", f"project_name={project_name}"])
            if project_slug:
                copier_args.extend(["-d", f"project_slug={project_slug}"])
            if preferred_adapter:
                copier_args.extend(["-d", f"preferred_adapter={preferred_adapter}"])
            if openspec_tools:
                copier_args.extend(["-d", f"openspec_tools={openspec_tools}"])
            if beads_prefix:
                copier_args.extend(["-d", f"beads_prefix={beads_prefix}"])
            if not init_beads:
                copier_args.extend(["-d", "init_beads=false"])
            if not init_git_repository:
                copier_args.extend(["-d", "init_git_repository=false"])
            return new_project(destination, resolve_project_template(template), copier_args)
        if command == "update-project":
            if args and args[0] in {"-h", "--help"}:
                print("Usage: update-project [destination] [options]")
                return 0
            destination = "."
            extra_args = []
            if args and not args[0].startswith("-"):
                destination = args[0]
                extra_args = args[1:]
            else:
                extra_args = args
            return update_project(destination, extra_args)
        die(f"unknown python-cli command: {command}")
    except CommandError as exc:
        if str(exc) != "help-requested":
            print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
