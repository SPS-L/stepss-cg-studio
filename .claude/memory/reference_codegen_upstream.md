---
name: Codegen Upstream Reference
description: stepss-Codegen repo — CLI invocation, DSL parsing rules, block Fortran sources, validation, dimension limits
type: reference
---

**Repo:** https://github.com/SPS-L/stepss-Codegen

## CLI Invocation
- `CODEGEN -tfilename.txt` — single file (no space between -t and filename)
- `CODEGEN -lfilelist.txt` — list of files
- `CODEGEN` (no args) — interactive prompt
- Output: `{type}_{name}.f90` in current directory

## Dimension Limits (modules.f90)
- Max name length: 20 chars (`mxcharname`)
- Max line length: 200 chars (`mxcharline`)
- Max expression length: 300 chars (`mxcharexpr`)
- Max data items: 500, max parameters: 100, max states: 500

## Validation Rules (fatal errors)
- Model type must be exc/tor/inj/twop
- All 6 sections in order: header, %data, %parameters, %states, %observables, %models
- No duplicate names across data/params/states
- States cannot use input variable names
- `{name}` must reference known data/parameter; `[name]` must reference known state/input
- Balanced braces/brackets required
- Mandatory outputs must appear in at least one block (isanoutput=true)
- Equation count must equal state count (indexf == indexx)
- `f_inj` only in inj models; `f_twop_bus1/2` only in twop models
- Input variables cannot be block outputs

## Block Source Structure
Each block is a Fortran file calling `getstate(.true./.false.)` and `getparam()` sequentially.
- `.true.` = registers as output (triggers mandatory output tracking for vf/tm/ix/iy)
- `.false.` = input state
- `getparam()` = data name, param name, or inline numeric expression

## Switch Block DSL Order (important quirk)
switch2/3/4/5: inputs first, then control signal (getstate .true.), then actual output (getstate .false.).
The variable read with isanoutput=true is the integer control selector, not the algebraic output.

## FSA Block Format
```
& fsa
{initial_state_number_expression}
#1
{algebraic equations}
->2
{transition condition}
#2
{algebraic equations}
->1
{transition condition}
##
```
