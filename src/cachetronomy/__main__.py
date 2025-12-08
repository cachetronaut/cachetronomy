from __future__ import annotations
import inspect
import typing
import textwrap
import os
import atexit

from typing import (
    Any,
    Callable,
    Literal,
    Union,
    get_args,
    get_origin,
)
from types import UnionType, NoneType
from pathlib import Path
from functools import wraps
from datetime import datetime
from dataclasses import dataclass, field

import typer

from rich.table import Table
from rich.style import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.pretty import pprint
from rich import box
from rich.traceback import install
from pydantic import BaseModel
from synchronaut.utils import set_request_ctx
from synchronaut import call_any

from cachetronomy import Cachetronaut
from cachetronomy import Profile
from cachetronomy.core.types.schemas import (
    AccessLogEntry,
    CacheEntry, 
    CacheMetadata,
    EvictionLogEntry,
    ExpiredEntry,
)

install()
console = Console()
app = typer.Typer(
    help='Cachetronomy CLI',
    add_completion=True,
    pretty_exceptions_show_locals=True,
    pretty_exceptions_short=True,
    chain=True
)
_SIMPLE_SCALARS = (str, int, float, bool, Path, Any)
_NONE = type(None)
_PYDANTIC_BASES = (
    Profile,
    CacheEntry,
    CacheMetadata,
    AccessLogEntry,
    EvictionLogEntry,
    ExpiredEntry,
    BaseModel
)

# ––– Dataclasses metadata models –––––––––––––––––––––––––––––––––––––––––––––


@dataclass
class TypeMeta():
    origin: type | None
    annotated: bool
    is_list: bool
    is_union: bool
    is_optional: bool
    is_pydantic: bool
    is_scalar: bool
    inner: Any | None
    args: list[Any] = field(default_factory=list)

    @classmethod
    def from_annotation(
        cls, 
        ann: Any, 
        pydantic_bases: tuple[type, ...]
    ) -> TypeMeta:
        origin = get_origin(ann)
        args = list(get_args(ann))

        # unwrap Annotated[T, ...]
        if origin is typing.Annotated:
            inner = args[0]
            origin, args = get_origin(inner), list(get_args(inner))
            annotated = True
        else:
            inner, annotated = None, False

        is_union = origin is Union or isinstance(ann, UnionType)
        is_scalar = (origin or ann) in _SIMPLE_SCALARS or (
            any(arg in _SIMPLE_SCALARS for arg in args)
        )
        is_pydantic = (
            inspect.isclass(ann) and issubclass(ann, pydantic_bases)
        ) or (is_union and 
                any(
                    inspect.isclass(arg) and issubclass(arg, pydantic_bases)
                    for arg in args if arg is not _NONE
                )
        )

        return cls(
            origin=origin,
            args=args,
            annotated=annotated,
            is_list = origin is list,
            is_union = is_union,
            is_optional = _NONE in args,
            is_pydantic = is_pydantic,
            is_scalar = is_scalar,
            inner = inner
        )


@dataclass
class SimpleSig():
    params: list[str]
    return_annotation: str
    classification: Literal['simple'] = 'simple'


@dataclass
class ComplexSig():
    params: dict[str, TypeMeta]
    return_type: TypeMeta
    classification: Literal['complex'] = 'complex'

Signature = SimpleSig | ComplexSig


@dataclass
class CommandMeta():
    '''All the introspected data needed to register a Typer command.'''
    name: str
    cmd_name: str
    is_callable: bool
    signature: Signature | None

    @classmethod
    def from_callable(
        cls,
        fn: Callable,
        pydantic_bases: tuple[type, ...]
    ) -> CommandMeta:
        name = fn.__name__
        cmd_name = name.replace('_','-')
        if not callable(fn):
            return cls(
                name=name, 
                cmd_name=cmd_name, 
                is_callable=False, 
                signature=None
            )

        sig = inspect.signature(fn)
        params = [
            param for param in sig.parameters.values() if param.name != 'self'
        ]

        def is_simple(param: inspect.Parameter) -> bool:
            if param.annotation is inspect._empty:
                return True
            type_meta = TypeMeta.from_annotation(
                                    param.annotation, 
                                    pydantic_bases
                                )
            
            is_simple = type_meta.is_scalar or (
                                                type_meta.is_optional and 
                                                type_meta.is_scalar
                                            ) or (
                                                type_meta.is_list and 
                                                type_meta.args and 
                                                type_meta.args[0] in _SIMPLE_SCALARS
                                            )
            return is_simple

        if all(is_simple(param) for param in params):
            return_annotation = repr(sig.return_annotation)
            simple = SimpleSig(
                params=[param.name for param in params],
                return_annotation=return_annotation
            )
            return cls(
                name=name, 
                cmd_name=cmd_name, 
                is_callable=True, 
                signature=simple
            )

        # complex
        param_metas = {
            param.name: TypeMeta.from_annotation(
                                    param.annotation, 
                                    pydantic_bases
                                ) for param in params
        }
        return_meta = TypeMeta.from_annotation(
                                    sig.return_annotation, 
                                    pydantic_bases
                                )
        complex_sig = ComplexSig(params=param_metas, return_type=return_meta)
        return cls(
            name=name, 
            cmd_name=cmd_name, 
            is_callable=True, 
            signature=complex_sig
        )


# ─── Framing & signature‐stripping helper ────────────────────────────────────

def normalize(cell: Any):
    if isinstance(cell, datetime):
        loc = cell.astimezone()
        return loc.strftime('%Y-%m-%d %H:%M:%S %Z')
    return cell

def to_output(obj: Any, cachetronaut: Cachetronaut | None = None, command_name: str | None = None) -> None:
    if cachetronaut:
        profile_name = cachetronaut.profile.name
        if command_name:
            norm_command_name = command_name.replace('_','-')
            title = f'{profile_name} cachetronaut → {norm_command_name}'
    else:
        title = None
    norm_rows = []
    output_style = Style(color='#8338EC', bold=True, encircle=True)

    if isinstance(obj, BaseModel):
        data = obj.model_dump()
        headers = list(data.keys())
        rows = [[data[header] for header in headers]]
        norm_rows = [[normalize(cell) for cell in row] for row in rows]

    elif isinstance(obj, list) and obj and isinstance(obj[0], BaseModel):
        headers = list(obj[0].model_dump().keys())
        rows = [
            [
                model.model_dump()[header] for header in headers
            ]   for model in obj
        ]
        norm_rows = [[normalize(cell) for cell in row] for row in rows]

    elif isinstance(obj, dict):
        headers = list(obj.keys())
        rows = [[obj[header] for header in headers]]
        norm_rows = [[normalize(cell) for cell in row] for row in rows]

    elif isinstance(obj, (list, tuple)) and len(obj) >= 1:
        headers = ['results']
        rows = [[item] for item in obj]
        norm_rows = [[normalize(cell) for cell in row] for row in rows]

    else:
        if isinstance(obj, str):
            obj_md = Markdown(obj)
            console.print(obj_md, justify='left', emoji=True, soft_wrap=True)
        else:
            pprint(obj)
        return

    table = Table(
        *headers,
        style=output_style,
        title=title,
        title_style=output_style,
        title_justify='center',
        show_header=bool(headers),
        header_style='bold',
        show_footer=False,
        footer_style='table.footer',
        show_edge=True,
        box=box.ROUNDED,
        show_lines=False,
        caption_style='none',
        caption_justify='center',
        expand=True,
        padding=(0,1),
        collapse_padding=False,
        pad_edge=True,
        highlight=True,
        leading=0,
    )

    if norm_rows:
        [(table.add_row(*[str(cell) for cell in row])) for row in norm_rows]

    console.print(table)


def build_short_flag(long_flag: str) -> str:
    '''
    Turn a long option like '--time-to-live' into its short form '-ttl'.
    '''
    name = long_flag.lstrip('-')
    parts = name.split('-')
    initials = ''.join(part[0] for part in parts if part)
    return f'-{initials}'

# ─── BOOL FLAG HELPER ────────────────────────────────────────────────────────

def build_bool_param_decls(
    name: str, 
    default: bool | None
) -> tuple[list[str], bool | None]:
    '''
    Given a flag name (no leading hyphens) and its default (True/False/None),
    return (decl-strings, canonical-default) following Typer’s rules:
      * default=False → only '--flag'
      * default=True → only ' /--no-flag'
      * default=None → '--flag/--no-flag'
    '''
    positive = f'--{name}'
    negative = f'--no-{name}'

    if default is True:
        return [f' /{negative}'], True
    elif default is None:
        return [f'{positive}/{negative}'], None
    else:
        return [positive], False

# ─── Auto‐registration routine ───────────────────────────────────────────────

def auto_register_object(
    app: typer.Typer,
    obj: Any,
    *,
    exclude: set[str] = frozenset(),
    pydantic_bases: tuple[type, ...] = (BaseModel,)
) -> None:
    '''
    Inspect all public methods on `obj`, skip names in `exclude`,
    and register each as a Typer command on `app`.
    Any Pydantic-model parameter is unpacked into its own flags.
    Bool and Optional[bool] params get --flag / --no-flag behavior.
    '''
    existing = {cmd.name for cmd in app.registered_commands}

    for name, member in inspect.getmembers(obj, predicate=inspect.ismethod):
        if name.startswith('_') or name in exclude:
            continue

        meta = CommandMeta.from_callable(member.__func__, pydantic_bases)
        if not meta.is_callable or meta.cmd_name in existing:
            continue

        sig = inspect.signature(member.__func__)
        new_params: list[inspect.Parameter] = []
        model_maps: dict[str, tuple[type, list[str]]] = {}

        # Add typer.Context as first parameter for all commands
        new_params.append(
            inspect.Parameter(
                name='ctx',
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=typer.Context
            )
        )

        for param in sig.parameters.values():
            if param.name == 'self':
                continue

            # any→str fallback
            if param.annotation is Any or param.annotation is typing.Any:
                param = param.replace(annotation=str, default=param.default)

            type_meta = (
                meta.signature.params[param.name]
                if isinstance(meta.signature, ComplexSig)
                else TypeMeta.from_annotation(param.annotation, pydantic_bases)
            )

            # ─── Pydantic‐model parameters ───────────────────────────────────

            if type_meta.is_pydantic:
                ann = param.annotation
                origin = get_origin(ann)
                args = get_args(ann)

                if origin is Union or isinstance(ann, UnionType):
                    candidates = [arg for arg in args if arg is not NoneType]
                else:
                    candidates = [ann]

                concrete = [
                    arg for arg in candidates
                    if inspect.isclass(arg)
                    and issubclass(arg, BaseModel)
                    and arg is not BaseModel
                ]

                if len(concrete) == 1:
                    model_cls = concrete[0]
                    field_names = list(model_cls.model_fields)
                    model_maps[param.name] = (model_cls, field_names)

                    for field in field_names:
                        field_info = model_cls.model_fields[field]
                        long_flag = f'--{field.replace('_', '-')}'
                        short_flag = build_short_flag(long_flag)

                        if field_info.is_required():
                            default = typer.Argument(
                                ...,
                                show_default=False,
                                metavar=field.upper(),
                                help=field_info.description,
                                show_choices=True,
                            )
                            kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
                        else:
                            if field_info.default_factory is not None:
                                default_val = field_info.default_factory()
                            else:
                                default_val = field_info.default

                            field_type_meta = TypeMeta.from_annotation(
                                field_info.annotation, pydantic_bases
                            )
                            is_bool_field = (
                                field_info.annotation is bool
                                or (
                                    field_type_meta.is_optional and 
                                    any(
                                        arg is bool 
                                        for arg in field_type_meta.args
                                    )
                                )
                            )

                            if is_bool_field:
                                flag_name = field.replace('_', '-')
                                param_decls, canon_default = build_bool_param_decls(
                                    flag_name, default_val
                                )
                                default = typer.Option(
                                    canon_default,
                                    *param_decls,
                                    help=f'[bool] {field_info.description}',
                                    show_default=True,
                                    show_choices=True,
                                )
                            else:
                                default = typer.Option(
                                    default_val,
                                    short_flag,
                                    long_flag,
                                    help=field_info.description,
                                    show_default=True,
                                    show_choices=True,
                                )
                            kind = inspect.Parameter.KEYWORD_ONLY

                        new_params.append(
                            inspect.Parameter(
                                name=field,
                                kind=kind,
                                annotation=field_info.annotation,
                                default=default,
                            )
                        )

            # ─── Non-Pydantic parameters ─────────────────────────────────────

            else:
                long_flag = f'--{param.name.replace('_', '-')}'
                short_flag = build_short_flag(long_flag)

                def _find_instance_name(obj: Any) -> str:
                    frame = inspect.currentframe()
                    
                    def _is_private(variable: str):
                        return variable.startswith('_')

                    try:
                        user_frame = frame.f_back.f_back
                        frame_locals = user_frame.f_locals.items()
                        for var_name, var_value in frame_locals:
                            if var_value is obj and not _is_private(var_name):
                                return var_name

                        frame_globals = user_frame.f_globals.items()
                        for var_name, var_value in frame_globals:
                            if var_value is obj and not _is_private(var_name):
                                return var_name
                    finally:
                        del frame

                    return obj.__class__.__name__.lower()

                obj_name = _find_instance_name(obj)
                help_text = f'Used by {obj_name} on {meta.cmd_name} command.'

                if param.default is inspect._empty:
                    default = typer.Argument(
                        ...,
                        help=help_text,
                        show_default=False,
                    )
                    kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
                else:
                    is_bool = (
                        param.annotation is bool
                        or (
                            type_meta.is_optional and 
                            any(arg is bool for arg in type_meta.args)
                        )
                    )
                    if is_bool:
                        flag_name = param.name.replace('_', '-')
                        raw_def = param.default
                        param_decls, canon_default = build_bool_param_decls(
                            flag_name, raw_def
                        )
                        default = typer.Option(
                            canon_default,
                            *param_decls,
                            help=f'[bool] {help_text}',
                            show_default=True,
                        )
                    else:
                        default = typer.Option(
                            param.default,
                            short_flag,
                            long_flag,
                            help=help_text,
                            show_default=True,
                        )
                    kind = inspect.Parameter.KEYWORD_ONLY

                new_params.append(
                    inspect.Parameter(
                        name=param.name,
                        kind=kind,
                        annotation=param.annotation,
                        default=default,
                    )
                )

        pydantic_param_names = list(model_maps.keys())

        @wraps(member.__func__)
        def wrapper(
            ctx: typer.Context,
            *args,
            __member_name=name,
            __model_maps=model_maps,
            __pydantic_names=pydantic_param_names,
            **kwargs
        ):
            # Get the cachetronaut instance from context
            cachetronaut = ctx.obj['cachetronaut']
            actual_member = getattr(cachetronaut, __member_name)

            # unpack any Pydantic models
            new_args = list(args)
            for param_name in __pydantic_names:
                model_cls, fields = __model_maps[param_name]
                model_kwargs = {field: kwargs.pop(field) for field in fields}
                clean_model_kwargs = {
                    key: value for key, value in model_kwargs.items()
                    if value is not None
                }
                new_args.append(model_cls(**clean_model_kwargs))

            result = actual_member(*new_args, **kwargs)
            if result is None or result == []:
                result_obj = dict(**kwargs)
                result_obj.update({'result': None})
                return to_output(result_obj, cachetronaut=cachetronaut, command_name=__member_name)

            return to_output(result, cachetronaut=cachetronaut, command_name=__member_name)

        wrapper.__signature__ = sig.replace(parameters=new_params)
        wrapper.__annotations__ = {
            param.name: param.annotation for param in new_params 
            if param.annotation is not inspect._empty
        }
        wrapper.__annotations__['return'] = sig.return_annotation

        app.command(name=meta.cmd_name)(wrapper)

@app.callback(invoke_without_command=True)
def _init_session(
        ctx: typer.Context,
        db_path: str | None = typer.Option(
                None,
                '--db-path',
                '-db',
                help='Path to the persistent data store; defaults to cachetronomy.db'
            )
    ):
    cachetronaut = Cachetronaut(db_path=db_path)
    ctx.obj = {'cachetronaut': cachetronaut}
    set_request_ctx({'cli_mode': True})

    # Register cleanup handler to ensure proper shutdown
    def cleanup():
        try:
            call_any(cachetronaut.shutdown)
        except (RuntimeError, Exception):
            # Event loop may already be closed, which is fine for CLI usage
            pass
    atexit.register(cleanup)

    profile, db_path = cachetronaut.store.get_config('active_profile')
    if profile and db_path:
        cachetronaut.store.set_config('active_profile', profile, db_path)

    cachetronaut.profile = profile
    cachetronaut.store.access_logger.batch_size = 1
    cachetronaut.store.eviction_logger.batch_size = 1

    if ctx.invoked_subcommand is None:
        main()

@app.command(name='main')
def main():
    '''🎉 Welcome to Cachetronomy CLI!'''
    link: str = 'https://github.com/cachetronaut/cachetronomy'
    welcome_message: str = f'''
    ## 👋 Hello, Cachetronaut! Welcome to Cachetronomy!💫
    - Not sure what to do?
    - Try entering `cachetronomy --help`
    - Or see documentation [here]({link})
    '''
    to_output(textwrap.dedent(welcome_message))

# Create a temporary instance for introspection only (not used at runtime)
_introspection_instance = Cachetronaut()
auto_register_object(
    app,
    _introspection_instance,
    exclude={
        'shutdown',
        'memory_keys',
        'memory_stats',
        'evict',
        'evict_all',
        'get_or_compute',  # Excluded: has Callable parameter (not CLI-compatible)
        'get_many',  # Excluded: dict types not CLI-compatible
        'set_many',  # Excluded: dict types not CLI-compatible
        'delete_many',  # Excluded: list types complex for CLI
        'health_check',  # Excluded: dict return type
        'stats',  # Excluded: dict return type
    },
    pydantic_bases=_PYDANTIC_BASES
)
# Note: We don't clean up the introspection instance as it's only used for
# method signature inspection at module load time

if __name__ == '__main__':
    app()