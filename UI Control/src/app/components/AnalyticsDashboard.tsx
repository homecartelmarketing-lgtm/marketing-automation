import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { TrendingUp, Users, Heart, MessageCircle, Share2 } from 'lucide-react';

interface AnalyticsData {
  platformMetrics: Array<{ platform: string; posts: number; engagement: number }>;
  weeklyEngagement: Array<{ day: string; likes: number; comments: number; shares: number }>;
  postPerformance: Array<{ name: string; value: number }>;
  totalStats: {
    totalPosts: number;
    totalEngagement: number;
    avgEngagement: number;
    followers: number;
  };
}

interface AnalyticsDashboardProps {
  data: AnalyticsData;
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042'];

export function AnalyticsDashboard({ data }: AnalyticsDashboardProps) {
  const stats = [
    {
      label: 'Total Posts',
      value: data.totalStats.totalPosts,
      icon: TrendingUp,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100',
    },
    {
      label: 'Total Engagement',
      value: data.totalStats.totalEngagement.toLocaleString(),
      icon: Heart,
      color: 'text-pink-600',
      bgColor: 'bg-pink-100',
    },
    {
      label: 'Avg. Engagement',
      value: data.totalStats.avgEngagement.toFixed(1),
      icon: MessageCircle,
      color: 'text-green-600',
      bgColor: 'bg-green-100',
    },
    {
      label: 'Followers',
      value: data.totalStats.followers.toLocaleString(),
      icon: Users,
      color: 'text-purple-600',
      bgColor: 'bg-purple-100',
    },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Analytics Dashboard</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div key={stat.label} className="bg-white rounded-lg shadow-md p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">{stat.label}</p>
                  <p className="text-2xl font-bold">{stat.value}</p>
                </div>
                <div className={`${stat.bgColor} p-3 rounded-lg`}>
                  <Icon className={`w-6 h-6 ${stat.color}`} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold mb-4">Weekly Engagement</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.weeklyEngagement} key="weekly-engagement-chart">
              <CartesianGrid strokeDasharray="3 3" key="grid-weekly" />
              <XAxis dataKey="day" key="xaxis-weekly" />
              <YAxis key="yaxis-weekly" />
              <Tooltip key="tooltip-weekly" />
              <Legend key="legend-weekly" />
              <Line key="line-likes" type="monotone" dataKey="likes" stroke="#ec4899" strokeWidth={2} name="Likes" />
              <Line key="line-comments" type="monotone" dataKey="comments" stroke="#3b82f6" strokeWidth={2} name="Comments" />
              <Line key="line-shares" type="monotone" dataKey="shares" stroke="#10b981" strokeWidth={2} name="Shares" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold mb-4">Platform Performance</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.platformMetrics} key="platform-performance-chart">
              <CartesianGrid strokeDasharray="3 3" key="grid-platform" />
              <XAxis dataKey="platform" key="xaxis-platform" />
              <YAxis key="yaxis-platform" />
              <Tooltip key="tooltip-platform" />
              <Legend key="legend-platform" />
              <Bar key="bar-posts" dataKey="posts" fill="#3b82f6" name="Posts" />
              <Bar key="bar-engagement" dataKey="engagement" fill="#10b981" name="Engagement" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold mb-4">Post Status Distribution</h3>
          {data.postPerformance.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart key="pie-chart-status">
                <Pie
                  key="pie-status"
                  data={data.postPerformance}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {data.postPerformance.map((entry, index) => (
                    <Cell key={`pie-cell-${entry.name}-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip key="tooltip-pie" />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[300px] flex items-center justify-center text-gray-400">
              <p>No posts yet. Start creating content to see analytics.</p>
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold mb-4">Top Performing Posts</h3>
          <div className="space-y-4">
            {[
              { platform: 'Instagram', content: 'Summer product launch', engagement: 2845, color: 'bg-pink-500' },
              { platform: 'Twitter', content: 'Industry insights thread', engagement: 1923, color: 'bg-blue-400' },
              { platform: 'LinkedIn', content: 'Company milestone update', engagement: 1567, color: 'bg-blue-700' },
              { platform: 'Facebook', content: 'Customer success story', engagement: 1234, color: 'bg-blue-600' },
            ].map((post, index) => (
              <div key={index} className="flex items-center gap-3">
                <div className={`w-2 h-12 ${post.color} rounded`} />
                <div className="flex-1">
                  <p className="font-medium text-sm">{post.content}</p>
                  <p className="text-xs text-gray-600">{post.platform}</p>
                </div>
                <div className="text-right">
                  <p className="font-semibold">{post.engagement}</p>
                  <p className="text-xs text-gray-600">engagements</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
