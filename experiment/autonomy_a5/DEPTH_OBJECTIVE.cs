using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using RoslynMcp.Core.Query.Utilities;
using Xunit;

namespace RoslynMcp.Core.Tests.Query.Utilities;

public class GenesisA5DepthOfInheritanceTests
{
    [Fact]
    public void CountsObjectRootAcrossClassStructAndDeeperChain()
    {
        const string source = """
            public class Root { }
            public class Child : Root { }
            public class GrandChild : Child { }
            public struct S { }
            """;

        var compilation = CSharpCompilation.Create("GenesisA5")
            .AddReferences(MetadataReference.CreateFromFile(typeof(object).Assembly.Location))
            .AddSyntaxTrees(CSharpSyntaxTree.ParseText(source));

        var root = compilation.GetTypeByMetadataName("Root")!;
        var child = compilation.GetTypeByMetadataName("Child")!;
        var grandChild = compilation.GetTypeByMetadataName("GrandChild")!;
        var valueStruct = compilation.GetTypeByMetadataName("S")!;

        Assert.Equal(1, MetricsCalculator.CalculateDepthOfInheritance(root));
        Assert.Equal(2, MetricsCalculator.CalculateDepthOfInheritance(child));
        Assert.Equal(3, MetricsCalculator.CalculateDepthOfInheritance(grandChild));
        Assert.Equal(2, MetricsCalculator.CalculateDepthOfInheritance(valueStruct));
        Assert.Equal(0, MetricsCalculator.CalculateDepthOfInheritance(null));
    }
}
