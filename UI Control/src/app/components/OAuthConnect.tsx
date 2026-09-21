import { useState, useEffect } from 'react';
import { X, Shield, CheckCircle, AlertCircle } from 'lucide-react';

interface OAuthConnectProps {
  platform: {
    id: string;
    name: string;
    icon: React.ComponentType<{ className?: string }>;
    color: string;
  };
  onSuccess: (data: { accessToken: string; refreshToken: string; username: string; userId: string; expiresIn: number }) => void;
  onCancel: () => void;
}

export function OAuthConnect({ platform, onSuccess, onCancel }: OAuthConnectProps) {
  const [step, setStep] = useState<'authorize' | 'loading' | 'success'>('authorize');
  const [permissions, setPermissions] = useState<string[]>([]);

  useEffect(() => {
    // Different platforms require different permissions
    const platformPermissions: Record<string, string[]> = {
      instagram: [
        'Read your profile information',
        'Access your posts and media',
        'Publish posts on your behalf',
        'View insights and analytics',
      ],
      tiktok: [
        'Read your profile information',
        'Access your videos',
        'Upload videos on your behalf',
        'View video analytics',
      ],
      twitter: [
        'Read your profile information',
        'Post tweets on your behalf',
        'Access direct messages',
        'View analytics',
      ],
      facebook: [
        'Read your profile information',
        'Manage your pages',
        'Publish posts on your behalf',
        'Access insights',
      ],
      linkedin: [
        'Read your profile information',
        'Share content on your behalf',
        'Access organization pages',
        'View analytics',
      ],
    };

    setPermissions(platformPermissions[platform.id] || []);
  }, [platform.id]);

  const handleAuthorize = async () => {
    setStep('loading');

    // Simulate OAuth flow
    // In production, this would:
    // 1. Redirect to platform's OAuth authorization URL
    // 2. User logs in on the platform's site
    // 3. Platform redirects back with authorization code
    // 4. Exchange code for access token

    await new Promise(resolve => setTimeout(resolve, 2000));

    // Simulate successful OAuth response
    const mockOAuthResponse = {
      accessToken: `${platform.id}_access_${Date.now()}`,
      refreshToken: `${platform.id}_refresh_${Date.now()}`,
      username: `demo_user_${Math.floor(Math.random() * 1000)}`,
      userId: `${platform.id}_${Date.now()}`,
      expiresIn: 3600, // 1 hour
    };

    setStep('success');

    setTimeout(() => {
      onSuccess(mockOAuthResponse);
    }, 1500);
  };

  const Icon = platform.icon;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div className="flex items-center gap-3">
            <div className={`${platform.color} p-2 rounded-full`}>
              <Icon className="w-6 h-6 text-white" />
            </div>
            <div>
              <h3 className="text-xl font-bold">Connect to {platform.name}</h3>
              <p className="text-sm text-gray-600">OAuth 2.0 Authorization</p>
            </div>
          </div>
          {step === 'authorize' && (
            <button
              onClick={onCancel}
              className="text-gray-400 hover:text-gray-600 transition"
            >
              <X className="w-6 h-6" />
            </button>
          )}
        </div>

        {/* Content */}
        <div className="p-6">
          {step === 'authorize' && (
            <>
              <div className="mb-6">
                <div className="flex items-center gap-2 mb-4 text-blue-600">
                  <Shield className="w-5 h-5" />
                  <span className="font-semibold">Permissions Requested</span>
                </div>
                <p className="text-sm text-gray-600 mb-4">
                  This application will be able to:
                </p>
                <ul className="space-y-2">
                  {permissions.map((permission, index) => (
                    <li key={index} className="flex items-start gap-2">
                      <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                      <span className="text-sm text-gray-700">{permission}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                <div className="flex gap-2">
                  <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div className="text-sm">
                    <p className="text-blue-900 font-medium mb-1">Secure Authentication</p>
                    <p className="text-blue-700">
                      You'll be redirected to {platform.name} to securely log in.
                      We never see your password.
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-4 mb-6">
                <p className="text-xs text-gray-600 leading-relaxed">
                  <strong>For Developers:</strong> In production, clicking "Authorize" would redirect to:
                  <code className="block mt-2 bg-white p-2 rounded text-xs border">
                    https://{platform.id}.com/oauth/authorize?
                    client_id=YOUR_APP_ID&
                    redirect_uri=YOUR_CALLBACK_URL&
                    scope=publish,read,analytics&
                    response_type=code
                  </code>
                </p>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={onCancel}
                  className="flex-1 px-4 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 transition font-medium"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAuthorize}
                  className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium"
                >
                  Authorize
                </button>
              </div>
            </>
          )}

          {step === 'loading' && (
            <div className="py-8 text-center">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-gray-200 border-t-blue-600 mb-4"></div>
              <h4 className="text-lg font-semibold mb-2">Connecting to {platform.name}</h4>
              <p className="text-sm text-gray-600">
                Redirecting to {platform.name} for authentication...
              </p>
              <div className="mt-6 bg-gray-50 rounded-lg p-4">
                <p className="text-xs text-gray-600">
                  <strong>In Production:</strong> User is redirected to {platform.name}'s login page,
                  then back to your app with an authorization code that gets exchanged for access tokens.
                </p>
              </div>
            </div>
          )}

          {step === 'success' && (
            <div className="py-8 text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-green-100 rounded-full mb-4">
                <CheckCircle className="w-8 h-8 text-green-600" />
              </div>
              <h4 className="text-lg font-semibold mb-2">Successfully Connected!</h4>
              <p className="text-sm text-gray-600">
                Your {platform.name} account has been linked
              </p>
            </div>
          )}
        </div>

        {/* Footer Info */}
        {step === 'authorize' && (
          <div className="px-6 py-4 bg-gray-50 border-t rounded-b-lg">
            <p className="text-xs text-gray-500 text-center">
              By authorizing, you agree to allow this app to access your {platform.name} account
              with the permissions listed above. You can revoke access anytime.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
