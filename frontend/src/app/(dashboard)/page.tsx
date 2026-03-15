"use client";

import { Search, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Header } from "@/components/layout/header";
import { MetricCard } from "@/components/dashboard/metric-card";
import { TrendingTopicsList } from "@/components/dashboard/trending-topics-list";
import { RecentArticlesList } from "@/components/dashboard/recent-articles-list";
import { useMetrics } from "@/hooks/use-metrics";
import { useTopics } from "@/hooks/use-topics";
import { useArticles } from "@/hooks/use-articles";

export default function DashboardPage() {
  const metrics = useMetrics();
  const topics = useTopics();
  const articles = useArticles();

  return (
    <div className="space-y-8">
      <Header
        title="Dashboard"
        subtitle="Monitor trends, track articles, and manage your content pipeline."
      >
        <Button variant="outline" size="sm">
          <Search className="mr-2 h-4 w-4" />
          Search
        </Button>
        <Button size="sm" className="bg-primary hover:bg-primary/90">
          <Zap className="mr-2 h-4 w-4" />
          New Scan
        </Button>
      </Header>

      {metrics.data && (
        <div className="grid grid-cols-4 gap-6">
          <MetricCard
            label="Topics Discovered"
            value={String(metrics.data.topics_discovered.value)}
            trend={metrics.data.topics_discovered.trend}
            trendDirection={metrics.data.topics_discovered.direction}
          />
          <MetricCard
            label="Articles Generated"
            value={String(metrics.data.articles_generated.value)}
            trend={metrics.data.articles_generated.trend}
            trendDirection={metrics.data.articles_generated.direction}
          />
          <MetricCard
            label="Avg Research Time"
            value={metrics.data.avg_research_time.value}
            trend={metrics.data.avg_research_time.trend}
            trendDirection={metrics.data.avg_research_time.direction}
            positiveDirection="down"
          />
          <MetricCard
            label="Published"
            value={String(metrics.data.published.value)}
            trend={metrics.data.published.trend}
            trendDirection={metrics.data.published.direction}
          />
        </div>
      )}

      <div className="grid grid-cols-2 gap-6">
        <TrendingTopicsList
          topics={topics.data ?? []}
          isLoading={topics.isLoading}
          isError={topics.isError}
          onRetry={() => topics.refetch()}
        />
        <RecentArticlesList
          articles={articles.data ?? []}
          isLoading={articles.isLoading}
          isError={articles.isError}
          onRetry={() => articles.refetch()}
        />
      </div>
    </div>
  );
}
