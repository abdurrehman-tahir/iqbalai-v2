import createSchemas from "../fixtures/openapi-create-schemas.json";

type JsonSchema = {
  properties?: Record<string, unknown>;
  required?: string[];
};

const schemas = createSchemas as Record<string, JsonSchema>;

export type ContractViolation = {
  schema: string;
  missingRequired: string[];
  unknownFields: string[];
};

/**
 * Check whether `payload` satisfies an OpenAPI create schema (required keys +
 * no fields outside `properties`). Returns violations instead of throwing so
 * tests can report all mismatches at once.
 */
export function checkOpenApiCreateContract(
  schemaName: string,
  payload: Record<string, unknown>,
): ContractViolation | null {
  const schema = schemas[schemaName];
  if (!schema) {
    throw new Error(`Unknown OpenAPI schema: ${schemaName}`);
  }

  const required = schema.required ?? [];
  const allowed = new Set(Object.keys(schema.properties ?? {}));

  const missingRequired = required.filter((key) => !(key in payload));
  const unknownFields = Object.keys(payload).filter((key) => !allowed.has(key));

  if (missingRequired.length === 0 && unknownFields.length === 0) {
    return null;
  }

  return { schema: schemaName, missingRequired, unknownFields };
}

export function formatContractViolation(v: ContractViolation): string {
  const parts: string[] = [`${v.schema} contract violated`];
  if (v.missingRequired.length) {
    parts.push(`missing required: ${v.missingRequired.join(", ")}`);
  }
  if (v.unknownFields.length) {
    parts.push(`unknown fields: ${v.unknownFields.join(", ")}`);
  }
  return parts.join("; ");
}
