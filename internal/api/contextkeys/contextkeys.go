package contextkeys

import "context"

// tenantContextKey is the context key for tenant_id.
type tenantContextKey struct{}

// WithTenantID stores tenantID in context.
func WithTenantID(ctx context.Context, tenantID string) context.Context {
	return context.WithValue(ctx, tenantContextKey{}, tenantID)
}

// TenantIDFromContext returns tenant_id from context when present.
func TenantIDFromContext(ctx context.Context) (string, bool) {
	v, ok := ctx.Value(tenantContextKey{}).(string)
	return v, ok
}
