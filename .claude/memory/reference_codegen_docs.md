---
name: Codegen Documentation Reference
description: stepss-docs repo — block reference docs, model type specs, built-in functions, DAE framework, expression syntax
type: reference
---

**Repo:** https://github.com/SPS-L/stepss-docs/

## Key Doc Paths
- `src/content/docs/developer/codegen-library.mdx` — complete block reference with equations
- `src/content/docs/developer/codegen-examples.mdx` — annotated model files for all 4 types
- `src/content/docs/developer/user-models.md` — DSL file format specification
- `src/content/docs/developer/uramses.mdx` — compilation/linking instructions
- `src/content/docs/models/custom-exciters.mdx` — all exc models
- `src/content/docs/models/custom-governors.mdx` — all tor models
- `src/content/docs/models/custom-injectors.mdx` — all inj models
- `src/content/docs/models/two-port-models.mdx` — all twop models

## Built-in Functions (available in expressions)
- `equal(var1, var2)` — returns 1.0 if |v1-v2| < 1e-6
- `ppower([vx],[vy],[ix],[iy])` — active power (inj only)
- `qpower([vx],[vy],[ix],[iy])` — reactive power (inj only)
- `vcomp([v],[p],[q],{Kv},{Rc},{Xc})` — voltage compensation (exc only)
- `satur([ve],{ve1},{se1},{ve2},{se2})` — saturation function (exc only)
- `vrectif([if],[vin],{kc})` — rectifier voltage drop (exc only)
- `vinrectif([if],[vrectif],{kc})` — inverse rectifier (exc only)

## Expression Syntax
- Fortran syntax: `**` for exponentiation, `dsqrt()`, `dcos()`, `dsin()`, `dlog10()`, etc.
- Boolean: `.lt.`, `.le.`, `.gt.`, `.ge.`, `.eq.`, `.ne.`
- `{name}` references data/parameters → becomes `prm(N)` in Fortran
- `[name]` references states/inputs → becomes `x(N)` or kept as-is for inputs
- `t` (bare) = simulation time variable

## DAE Framework
T * dx/dt = f(x, x_IN, u, z) where T diagonal (0 = algebraic, nonzero = differential).
Equation count must equal state count. Discrete variables z handle limiter states, automaton states.

## Model Type Reserved Data
- `inj`: `{sbase}` is reserved
- `twop`: `{sbase1}`, `{sbase2}` are reserved
