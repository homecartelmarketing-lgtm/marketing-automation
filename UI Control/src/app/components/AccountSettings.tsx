import { useState } from 'react';
import { Instagram, Twitter, Facebook, Linkedin, Music, CheckCircle, XCircle, Link as LinkIcon, Key } from 'lucide-react';
import { OAuthConnect } from './OAuthConnect';

interface SocialAccount {
  platform: 'instagram' | 'twitter' | 'facebook' | 'linkedin' | 'tiktok';
  name: string;
  icon: typeof Instagram;
  color: string;
  bgColor: string;
  connected: boolean;
  username?: string;
  followers?: number;
  accessToken?: string;
  refreshToken?: string;
  userId?: string;
  tokenExpiry?: number;
}

export function AccountSettings() {
  const [accounts, setAccounts] = useState<SocialAccount[]>([
    {
      platform: 'instagram',
      name: 'Instagram',
      icon: Instagram,
      color: 'text-pink-600',
      bgColor: 'bg-pink-500',
      connected: false,
    },
    {
      platform: 'tiktok',
      name: 'TikTok',
      icon: Music,
      color: 'text-black',
      bgColor: 'bg-black',
      connected: false,
    },
    {
      platform: 'twitter',
      name: 'Twitter',
      icon: Twitter,
      color: 'text-blue-400',
      bgColor: 'bg-blue-400',
      connected: false,
    },
    {
      platform: 'facebook',
      name: 'Facebook',
      icon: Facebook,
      color: 'text-blue-600',
      bgColor: 'bg-blue-600',
      connected: false,
    },
    {
      platform: 'linkedin',
      name: 'LinkedIn',
      icon: Linkedin,
      color: 'text-blue-700',
      bgColor: 'bg-blue-700',
      connected: false,
    },
  ]);

  const [showOAuthModal, setShowOAuthModal] = useState(false);
  const [selectedPlatform, setSelectedPlatform] = useState<SocialAccount | null>(null);

  const handleConnect = (account: SocialAccount) => {
    setSelectedPlatform(account);
    setShowOAuthModal(true);
  };

  const handleDisconnect = (platform: string) => {
    if (confirm('Are you sure you want to disconnect this account? This will revoke all permissions.')) {
      setAccounts(accounts.map(acc =>
        acc.platform === platform
          ? {
              ...acc,
              connected: false,
              username: undefined,
              followers: undefined,
              accessToken: undefined,
              refreshToken: undefined,
              userId: undefined,
              tokenExpiry: undefined
            }
          : acc
      ));
    }
  };

  const handleOAuthSuccess = (data: {
    accessToken: string;
    refreshToken: string;
    username: string;
    userId: string;
    expiresIn: number;
  }) => {
    if (!selectedPlatform) return;

    const expiryTime = Date.now() + (data.expiresIn * 1000);

    setAccounts(accounts.map(acc =>
      acc.platform === selectedPlatform.platform
        ? {
            ...acc,
            connected: true,
            username: data.username,
            followers: Math.floor(Math.random() * 50000) + 1000,
            accessToken: data.accessToken,
            refreshToken: data.refreshToken,
            userId: data.userId,
            tokenExpiry: expiryTime,
          }
        : acc
    ));

    setShowOAuthModal(false);
    setSelectedPlatform(null);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-2">Connected Accounts</h2>
        <p className="text-gray-600">Link your social media accounts to start scheduling posts</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {accounts.map((account) => {
          const Icon = account.icon;

          return (
            <div key={account.platform} className="bg-white rounded-lg shadow-md p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-4">
                  <div className={`${account.bgColor} p-3 rounded-full`}>
                    <Icon className="w-8 h-8 text-white" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold">{account.name}</h3>
                    {account.connected ? (
                      <div className="flex items-center gap-1 text-green-600 text-sm">
                        <CheckCircle className="w-4 h-4" />
                        Connected
                      </div>
                    ) : (
                      <div className="flex items-center gap-1 text-gray-500 text-sm">
                        <XCircle className="w-4 h-4" />
                        Not connected
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {account.connected ? (
                <div className="space-y-3">
                  <div className="bg-gray-50 rounded-lg p-4">
                    <p className="text-sm text-gray-600">Username</p>
                    <p className="font-semibold">@{account.username}</p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-4">
                    <p className="text-sm text-gray-600">Followers</p>
                    <p className="font-semibold">{account.followers?.toLocaleString()}</p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <Key className="w-4 h-4 text-gray-500" />
                      <p className="text-sm text-gray-600">Access Token</p>
                    </div>
                    <p className="font-mono text-xs text-gray-800 truncate">
                      {account.accessToken?.substring(0, 30)}...
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      Expires: {account.tokenExpiry ? new Date(account.tokenExpiry).toLocaleString() : 'N/A'}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDisconnect(account.platform)}
                    className="w-full px-4 py-2 border border-red-300 text-red-600 rounded-lg hover:bg-red-50 transition"
                  >
                    Revoke Access
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => handleConnect(account)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
                >
                  <LinkIcon className="w-4 h-4" />
                  Connect with OAuth
                </button>
              )}
            </div>
          );
        })}
      </div>

      {showOAuthModal && selectedPlatform && (
        <OAuthConnect
          platform={{
            id: selectedPlatform.platform,
            name: selectedPlatform.name,
            icon: selectedPlatform.icon,
            color: selectedPlatform.bgColor,
          }}
          onSuccess={handleOAuthSuccess}
          onCancel={() => {
            setShowOAuthModal(false);
            setSelectedPlatform(null);
          }}
        />
      )}
    </div>
  );
}
