/**
 * Safe arithmetic for mini-sim output expressions (T-191).
 *
 * TS port of `api/app/features/concept_enrichment/sim_expression.py` — the
 * two MUST accept the same grammar. Model output is never executed: only
 * numbers, declared variable names, + - * / ^, parentheses and unary minus.
 *
 *   expr   := term (('+' | '-') term)*
 *   term   := factor (('*' | '/') factor)*
 *   factor := unary ('^' factor)?        // right-associative
 *   unary  := '-' unary | atom
 *   atom   := NUMBER | NAME | '(' expr ')'
 */

export class ExpressionError extends Error {}

const TOKEN = /\s*(?:(\d+(?:\.\d+)?)|([a-z][a-z0-9_]*)|(\S))/y;
const MAX_TOKENS = 64;

function tokenize(source: string): string[] {
  const text = source.trim();
  const tokens: string[] = [];
  TOKEN.lastIndex = 0;
  while (TOKEN.lastIndex < text.length) {
    const match = TOKEN.exec(text);
    if (!match) throw new ExpressionError("unexpected character");
    const [, number, name, symbol] = match;
    if (symbol !== undefined && !"+-*/^()".includes(symbol)) {
      throw new ExpressionError(`unsupported symbol ${symbol}`);
    }
    tokens.push(number ?? name ?? symbol!);
    if (tokens.length > MAX_TOKENS)
      throw new ExpressionError("expression too long");
  }
  if (tokens.length === 0) throw new ExpressionError("empty expression");
  return tokens;
}

class Parser {
  private i = 0;
  constructor(
    private readonly tokens: string[],
    private readonly values: Record<string, number>,
  ) {}

  private peek(): string | undefined {
    return this.tokens[this.i];
  }

  private take(): string {
    const token = this.tokens[this.i];
    if (token === undefined)
      throw new ExpressionError("unexpected end of expression");
    this.i += 1;
    return token;
  }

  parse(): number {
    const value = this.expr();
    if (this.peek() !== undefined) throw new ExpressionError("trailing tokens");
    return value;
  }

  private expr(): number {
    let value = this.term();
    while (this.peek() === "+" || this.peek() === "-") {
      const op = this.take();
      const rhs = this.term();
      value = op === "+" ? value + rhs : value - rhs;
    }
    return value;
  }

  private term(): number {
    let value = this.factor();
    while (this.peek() === "*" || this.peek() === "/") {
      const op = this.take();
      const rhs = this.factor();
      value = op === "*" ? value * rhs : value / rhs;
    }
    return value;
  }

  private factor(): number {
    const base = this.unary();
    if (this.peek() === "^") {
      this.take();
      const exponent = this.factor();
      if (base < 0 && !Number.isInteger(exponent))
        throw new ExpressionError("complex result");
      return Math.pow(base, exponent);
    }
    return base;
  }

  private unary(): number {
    if (this.peek() === "-") {
      this.take();
      return -this.unary();
    }
    return this.atom();
  }

  private atom(): number {
    const token = this.take();
    if (token === "(") {
      const value = this.expr();
      if (this.take() !== ")") throw new ExpressionError("missing )");
      return value;
    }
    if (/^\d/.test(token)) return Number(token);
    if (/^[a-z]/.test(token)) {
      if (!(token in this.values))
        throw new ExpressionError(`unknown variable ${token}`);
      return this.values[token];
    }
    throw new ExpressionError(`unexpected token ${token}`);
  }
}

/** Value of the expression, or `null` where it is undefined (÷0, ±∞, NaN). */
export function evaluateExpression(
  expression: string,
  values: Record<string, number>,
): number | null {
  const result = new Parser(tokenize(expression), values).parse();
  return Number.isFinite(result) ? result : null;
}
