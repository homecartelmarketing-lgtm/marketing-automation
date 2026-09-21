import { useState } from 'react';
import { Calendar as CalendarIcon, Instagram, Twitter, Facebook, Linkedin, Music, Plus, Edit2, Trash2 } from 'lucide-react';
import { format, startOfMonth, endOfMonth, eachDayOfInterval, isSameDay, addMonths, subMonths } from 'date-fns';

interface Post {
  id: string;
  platform: 'instagram' | 'twitter' | 'facebook' | 'linkedin' | 'tiktok';
  content: string;
  scheduledDate: Date;
  status: 'draft' | 'scheduled' | 'published';
  imageUrl?: string;
}

interface ContentCalendarProps {
  posts: Post[];
  onAddPost: (date: Date) => void;
  onEditPost: (post: Post) => void;
  onDeletePost: (id: string) => void;
}

const platformIcons = {
  instagram: Instagram,
  tiktok: Music,
  twitter: Twitter,
  facebook: Facebook,
  linkedin: Linkedin,
};

const platformColors = {
  instagram: 'bg-pink-500',
  tiktok: 'bg-black',
  twitter: 'bg-blue-400',
  facebook: 'bg-blue-600',
  linkedin: 'bg-blue-700',
};

export function ContentCalendar({ posts, onAddPost, onEditPost, onDeletePost }: ContentCalendarProps) {
  const [currentDate, setCurrentDate] = useState(new Date());

  const monthStart = startOfMonth(currentDate);
  const monthEnd = endOfMonth(currentDate);
  const daysInMonth = eachDayOfInterval({ start: monthStart, end: monthEnd });

  const getPostsForDay = (day: Date) => {
    return posts.filter(post => isSameDay(new Date(post.scheduledDate), day));
  };

  const previousMonth = () => setCurrentDate(subMonths(currentDate, 1));
  const nextMonth = () => setCurrentDate(addMonths(currentDate, 1));

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <CalendarIcon className="w-6 h-6" />
          Content Calendar
        </h2>
        <div className="flex items-center gap-4">
          <button
            onClick={previousMonth}
            className="px-3 py-1 rounded hover:bg-gray-100 transition"
          >
            ←
          </button>
          <span className="font-semibold min-w-[150px] text-center">
            {format(currentDate, 'MMMM yyyy')}
          </span>
          <button
            onClick={nextMonth}
            className="px-3 py-1 rounded hover:bg-gray-100 transition"
          >
            →
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-2">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
          <div key={day} className="text-center font-semibold text-gray-600 py-2">
            {day}
          </div>
        ))}

        {Array.from({ length: monthStart.getDay() }).map((_, i) => (
          <div key={`empty-${i}`} className="min-h-[120px] bg-gray-50 rounded" />
        ))}

        {daysInMonth.map(day => {
          const dayPosts = getPostsForDay(day);
          const isToday = isSameDay(day, new Date());

          return (
            <div
              key={day.toISOString()}
              className={`min-h-[120px] border rounded-lg p-2 hover:border-blue-400 transition ${
                isToday ? 'border-blue-500 bg-blue-50' : 'border-gray-200 bg-white'
              }`}
            >
              <div className="flex justify-between items-start mb-2">
                <span className={`text-sm font-semibold ${isToday ? 'text-blue-600' : 'text-gray-700'}`}>
                  {format(day, 'd')}
                </span>
                <button
                  onClick={() => onAddPost(day)}
                  className="text-gray-400 hover:text-blue-500 transition"
                  title="Add post"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-1">
                {dayPosts.map(post => {
                  const Icon = platformIcons[post.platform];
                  return (
                    <div
                      key={post.id}
                      className="group relative bg-gray-50 rounded p-1.5 text-xs hover:bg-gray-100 transition cursor-pointer"
                      onClick={() => onEditPost(post)}
                    >
                      <div className="flex items-center gap-1">
                        <Icon className={`w-3 h-3 text-white ${platformColors[post.platform]} rounded p-0.5`} />
                        <span className="truncate flex-1">{post.content}</span>
                      </div>
                      <div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 flex gap-1">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onEditPost(post);
                          }}
                          className="p-0.5 bg-white rounded hover:bg-blue-100"
                        >
                          <Edit2 className="w-3 h-3 text-blue-600" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onDeletePost(post.id);
                          }}
                          className="p-0.5 bg-white rounded hover:bg-red-100"
                        >
                          <Trash2 className="w-3 h-3 text-red-600" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
