public class StarterApi
{
    public static void Main(string[] args)
    {
        CreateApp(args).Run();
    }

    public static WebApplication CreateApp(string[] args, Action<WebApplicationBuilder>? configure = null)
    {
        var builder = WebApplication.CreateBuilder(args);
        configure?.Invoke(builder);
        var app = builder.Build();
        app.MapGet("/health/live", () => new { status = "ok" });
        app.MapGet("/health/ready", () => new { status = "ok", backend = "demo" });
        app.MapGet("/v1/orders", () => new[] {
            new { id = "demo-001", customerId = "cust-001", currency = "GBP", total = 5 }
        });
        app.MapGet("/docs", () => new {
            description = "Read-only ASP.NET Core starter",
            endpoints = new[] { "/health/live", "/health/ready", "/v1/orders" }
        });
        return app;
    }
}
