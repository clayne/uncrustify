#!/usr/bin/env python

import argparse
import io
import os
import re

re_enum_decl = re.compile(r'enum class (\w+)( *// *<(\w+)>)?')
re_enum_value = re.compile(r'(\w+)(?= *([,=]|//|$))')
re_values = re.compile(r'UNC_OPTVALS\((\w+)\)')
re_aliases = re.compile(r'UNC_OPTVAL_ALIAS\(([^)]+)\)')
enums = {}
values = {}

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
script = os.path.relpath(__file__, root)


# =============================================================================
class Enumeration(object):
    # -------------------------------------------------------------------------
    def __init__(self, name, prefix, f):
        self.name = name
        self.prefix = prefix

        self.values = []
        self.value_aliases = {}

        self.convert_internal = False

        for line in iter(f.readline, ''):
            line = line.strip()

            if line.startswith('{'):
                for line in iter(f.readline, ''):
                    line = line.strip()
                    if line.startswith('};'):
                        return

                    if 'UNC_INTERNAL' in line:
                        return

                    if 'UNC_CONVERT_INTERNAL' in line:
                        self.convert_internal = True
                        continue

                    mv = re_enum_value.match(line)
                    if mv is not None:
                        v = mv.group(1)
                        self.values.append(v)
                        self.value_aliases[v] = [v.lower()]

    # -------------------------------------------------------------------------
    def add_aliases(self, value, *args):
        aliases = [x[1:-1] for x in args]  # strip quotes
        self.value_aliases[value] += aliases

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


# -----------------------------------------------------------------------------
def enum_value(enum, value):
    if enum.prefix is not None:
        return u'{}_{}'.format(enum.prefix, value)
    return value

# -----------------------------------------------------------------------------
def write_banner(out, args):
    out.write(
        u'/**\n'
        u' * @file {out_name}\n'
        u' * Helpers for option enumerators.\n'
        u' * Automatically generated by <code>{script}</code>\n'
        u' * from {in_name}.\n'
        u' */\n'
        u'\n'.format(
            in_name=os.path.basename(args.header),
            out_name=os.path.basename(args.output),
            script=script))


# -----------------------------------------------------------------------------
def write_value_strings(out, args):
    for vn, vs in values.items():
        out.write(u'const char *const {}_values[] = {{\n'.format(vn))
        out.write(u'{}\n   nullptr\n}};\n\n'.format(
            u'\n'.join([u'   "{}",'.format(x.lower()) for x in vs])))


# -----------------------------------------------------------------------------
def write_aliases(out, args):
    for enum in enums.values():
        if enum.prefix is None:
            continue

        for v in enum.values:
            out.write(u'constexpr auto {p}_{v} = {n}::{v};\n'.format(
                p=enum.prefix, n=enum.name, v=v))

        out.write(u'\n')


# -----------------------------------------------------------------------------
def write_conversions(out, args):
    header = u'\n//{}\n'.format('-' * 77)

    for enum in enums.values():
        if enum.convert_internal:
            continue

        out.write(header)
        out.write(
            u'bool convert_string(const char *in, {} &out)\n'.format(
                enum.name))
        out.write(
            u'{\n'
            u'   if (false)\n'
            u'   {\n'
            u'   }\n')

        for v in enum.values:
            for a in enum.value_aliases[v]:
                out.write(
                    u'   else if (strcasecmp(in, "{}") == 0)\n'
                    u'   {{\n'
                    u'      out = {};\n'
                    u'      return(true);\n'
                    u'   }}\n'.format(a, enum_value(enum, v)))

        out.write(
            u'   else\n'
            u'   {\n'
            u'      return(false);\n'
            u'   }\n'
            u'}\n\n')

    for enum in enums.values():
        out.write(header)
        out.write(u'const char *to_string({} val)\n'.format(enum.name))
        out.write(u'{\n'
                  u'   switch (val)\n'
                  u'   {\n')

        for v in enum.values:
            vs = v if enum.convert_internal else v.lower()
            out.write(
                u'   case {}:\n'
                u'      return "{}";\n\n'.format(
                    enum_value(enum, v), vs))

        out.write(
            u'   default:\n'
            u'      fprintf(stderr, "%s: Unknown {} \'%d\'\\n",\n'
            u'              __func__, static_cast<int>(val));\n'
            u'      log_flush(true);\n'
            u'      exit(EX_SOFTWARE);\n'
            u'   }}\n'
            u'}}\n\n'.format(enum.name))


# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='Generate options.cpp')
    parser.add_argument('output', type=str,
                        help='location of options.cpp to write')
    parser.add_argument('header', type=str,
                        help='location of options.h to read')
    parser.add_argument('template', type=str,
                        help='location of option_enum.cpp.in '
                             'to use as template')
    args = parser.parse_args()

    with io.open(args.header, 'rt', encoding='utf-8') as f:
        for line in iter(f.readline, ''):
            line = line.strip()

            me = re_enum_decl.match(line)
            if me is not None:
                e = Enumeration(me.group(1), me.group(3), f)
                enums[e.name] = e
                continue

            mv = re_values.match(line)
            if mv is not None:
                enum_name = mv.group(1)
                enum = enums['{}_e'.format(enum_name)]
                values[enum_name] = enum.values

            ma = re_aliases.match(line)
            if ma is not None:
                alias_args = [x.strip() for x in ma.group(1).split(',')]
                enum = enums[alias_args[0]]
                enum.add_aliases(*alias_args[1:])

    replacements = {
        u'##BANNER##': write_banner,
        u'##VALUE_STRINGS##': write_value_strings,
        u'##ALIASES##': write_aliases,
        u'##CONVERSIONS##': write_conversions,
    }

    with io.open(args.output, 'wt', encoding='utf-8') as out:
        with io.open(args.template, 'rt', encoding='utf-8') as t:
            for line in t:
                directive = line.strip()
                if directive in replacements:
                    replacements[directive](out, args)
                else:
                    out.write(line)


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

if __name__ == '__main__':
    main()