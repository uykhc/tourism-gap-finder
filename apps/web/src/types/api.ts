export interface ApiFieldError {
  field: string;
  message: string;
}

export class ApiError extends Error {
  readonly status: number | undefined;
  readonly fields: ApiFieldError[];

  constructor(
    message: string,
    status: number | undefined,
    fields: ApiFieldError[] = []
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.fields = fields;
  }
}
