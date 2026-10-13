using Microsoft.AspNetCore.TestHost;
using System.Text.Json;

await using var app = StarterApi.CreateApp([], builder => builder.WebHost.UseTestServer());
await app.StartAsync();
using var client = app.GetTestClient();
foreach (var path in new[] { "/health/live", "/health/ready", "/v1/orders", "/docs" })
{
    var response = await client.GetAsync(path);
    response.EnsureSuccessStatusCode();
    using var document = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
}
var missing = await client.GetAsync("/missing");
if (missing.StatusCode != System.Net.HttpStatusCode.NotFound)
    throw new Exception("Missing routes must return 404.");
