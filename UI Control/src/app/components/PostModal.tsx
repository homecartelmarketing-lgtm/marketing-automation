import { useState, useEffect } from 'react';
import { X, Instagram, Twitter, Facebook, Linkedin, Music, Calendar, Image as ImageIcon } from 'lucide-react';
import { format } from 'date-fns';

interface Post {
  id: string;
  platform: 'instagram' | 'twitter' | 'facebook' | 'linkedin' | 'tiktok';
  content: string;
  scheduledDate: Date;
  status: 'draft' | 'scheduled' | 'published';
  imageUrl?: string;
}

interface PostModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (post: Omit<Post, 'id'> | Post) => void;
  initialPost?: Post;
  initialDate?: Date;
}

const platforms = [
  { id: 'instagram' as const, name: 'Instagram', icon: Instagram, color: 'bg-pink-500' },
  { id: 'tiktok' as const, name: 'TikTok', icon: Music, color: 'bg-black' },
  { id: 'twitter' as const, name: 'Twitter', icon: Twitter, color: 'bg-blue-400' },
  { id: 'facebook' as const, name: 'Facebook', icon: Facebook, color: 'bg-blue-600' },
  { id: 'linkedin' as const, name: 'LinkedIn', icon: Linkedin, color: 'bg-blue-700' },
];

export function PostModal({ isOpen, onClose, onSave, initialPost, initialDate }: PostModalProps) {
  const [platform, setPlatform] = useState<'instagram' | 'twitter' | 'facebook' | 'linkedin' | 'tiktok'>('instagram');
  const [content, setContent] = useState('');
  const [scheduledDate, setScheduledDate] = useState('');
  const [scheduledTime, setScheduledTime] = useState('12:00');
  const [status, setStatus] = useState<'draft' | 'scheduled' | 'published'>('scheduled');
  const [imageUrl, setImageUrl] = useState('');

  useEffect(() => {
    if (initialPost) {
      setPlatform(initialPost.platform);
      setContent(initialPost.content);
      setStatus(initialPost.status);
      setImageUrl(initialPost.imageUrl || '');
      const date = new Date(initialPost.scheduledDate);
      setScheduledDate(format(date, 'yyyy-MM-dd'));
      setScheduledTime(format(date, 'HH:mm'));
    } else if (initialDate) {
      setScheduledDate(format(initialDate, 'yyyy-MM-dd'));
    }
  }, [initialPost, initialDate]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const dateTime = new Date(`${scheduledDate}T${scheduledTime}`);

    const postData = {
      platform,
      content,
      scheduledDate: dateTime,
      status,
      imageUrl: imageUrl || undefined,
    };

    if (initialPost) {
      onSave({ ...postData, id: initialPost.id });
    } else {
      onSave(postData);
    }

    onClose();
    resetForm();
  };

  const resetForm = () => {
    setPlatform('instagram');
    setContent('');
    setScheduledDate('');
    setScheduledTime('12:00');
    setStatus('scheduled');
    setImageUrl('');
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b">
          <h3 className="text-xl font-bold">
            {initialPost ? 'Edit Post' : 'Create New Post'}
          </h3>
          <button
            onClick={() => {
              onClose();
              resetForm();
            }}
            className="text-gray-400 hover:text-gray-600 transition"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          <div>
            <label className="block text-sm font-semibold mb-3">Select Platform</label>
            <div className="grid grid-cols-5 gap-3">
              {platforms.map(({ id, name, icon: Icon, color }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setPlatform(id)}
                  className={`flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition ${
                    platform === id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className={`${color} p-2 rounded-full`}>
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                  <span className="text-sm font-medium">{name}</span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-semibold mb-2">Post Content</label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              required
              rows={4}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="What's on your mind?"
            />
            <p className="text-xs text-gray-500 mt-1">{content.length} characters</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold mb-2">Schedule Date</label>
              <input
                type="date"
                value={scheduledDate}
                onChange={(e) => setScheduledDate(e.target.value)}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold mb-2">Schedule Time</label>
              <input
                type="time"
                value={scheduledTime}
                onChange={(e) => setScheduledTime(e.target.value)}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-semibold mb-2">Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as 'draft' | 'scheduled' | 'published')}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="draft">Draft</option>
              <option value="scheduled">Scheduled</option>
              <option value="published">Published</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-semibold mb-2">Image URL (Optional)</label>
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <ImageIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="url"
                  value={imageUrl}
                  onChange={(e) => setImageUrl(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="https://example.com/image.jpg"
                />
              </div>
            </div>
          </div>

          <div className="flex gap-3 justify-end pt-4 border-t">
            <button
              type="button"
              onClick={() => {
                onClose();
                resetForm();
              }}
              className="px-6 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
            >
              {initialPost ? 'Update Post' : 'Create Post'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
