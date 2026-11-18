import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from 'react';
import { Appearance } from 'react-native';

import { api, ApiError, setRefreshHandler, setSuspensionHandler } from '../api/client';
import { startRealtime, stopRealtime, subscribeRealtime } from '../api/realtime';
import {
  defaultAccessibility,
  loadAccessibility,
  saveAccessibility,
  type AccessibilityPreferences,
} from '../accessibility';
import type {
  Availability,
  Badge,
  Band,
  Booking,
  Clan,
  ClanMember,
  ClanMessage,
  Friend,
  LobbyInvite,
  MatchSummary,
  Mission,
  ModerationAction,
  ModerationAppeal,
  MyRating,
  Network,
  Notification,
  PassPlan,
  PassSubscription,
  Profile,
  Progress,
  QueueEntry,
  Sport,
  Stats,
  TicketPack,
  Track,
  Wallet,
  Venue,
} from '../api/types';
import {
  clearSession,
  loadSession,
  refreshStoredSession,
  saveSession,
  type Session,
} from '../session';

export type OnboardingState = {
  formats: string[];
  level: string;
  courtPreference: string;
  windows: Availability[];
  displayName: string;
  avatar: {
    skin: string;
    hair: string;
    shirt: string;
    style: 1 | 2 | 3;
    glasses: boolean;
  };
};

export type AuthState = {
  purpose: 'registration' | 'login' | 'password_reset';
  phone: string;
  email: string;
  challengeId: string | null;
  verifiedChallengeId: string | null;
};

type AppValue = {
  ready: boolean;
  hydrated: boolean;
  session: Session | null;
  dark: boolean;
  setDark: (value: boolean) => void;
  auth: AuthState;
  setAuth: (patch: Partial<AuthState>) => void;
  onboarding: OnboardingState;
  setOnboarding: (patch: Partial<OnboardingState>) => void;
  catalog: Sport[];
  profile: Profile | null;
  wallet: Wallet | null;
  progress: Progress | null;
  track: Track | null;
  badges: Badge[];
  missions: Mission[];
  matches: MatchSummary[];
  queue: QueueEntry | null;
  ratings: Record<string, MyRating>;
  packs: TicketPack[];
  pass: PassSubscription | null;
  passPlans: PassPlan[];
  bands: Band[];
  venues: Venue[];
  friends: Friend[];
  invites: LobbyInvite[];
  clan: Clan | null;
  clanMembers: ClanMember[];
  clanMessages: ClanMessage[];
  stats: Stats | null;
  network: Network | null;
  bookings: Booking[];
  notifications: Notification[];
  unreadNotifications: number;
  suspended: boolean;
  moderationActions: ModerationAction[];
  moderationAppeals: ModerationAppeal[];
  email: string | null;
  emailReady: boolean;
  accessibility: AccessibilityPreferences;
  setAccessibility: (preferences: AccessibilityPreferences) => Promise<void>;
  setSession: (tokens: Parameters<typeof saveSession>[0]) => Promise<void>;
  signOut: () => Promise<void>;
  setProfile: (profile: Profile | null) => void;
  setPass: (pass: PassSubscription | null) => void;
  setClan: (clan: Clan | null) => void;
  setMatches: (matches: MatchSummary[]) => void;
  setQueue: (queue: QueueEntry | null) => void;
  loadCatalog: () => Promise<Sport[]>;
  loadProfile: () => Promise<Profile | null>;
  loadWallet: () => Promise<Wallet | null>;
  loadSeason: () => Promise<void>;
  loadMatches: () => Promise<MatchSummary[]>;
  loadQueue: () => Promise<QueueEntry | null>;
  loadStore: () => Promise<void>;
  loadPass: () => Promise<void>;
  loadSocial: () => Promise<void>;
  loadClan: () => Promise<void>;
  loadClanMessages: (clanId: string) => Promise<ClanMessage[]>;
  loadStats: () => Promise<void>;
  loadVenues: () => Promise<Venue[]>;
  loadBookings: () => Promise<Booking[]>;
  loadNotifications: () => Promise<void>;
  markNotificationRead: (notificationId: string) => Promise<void>;
  markAllNotificationsRead: () => Promise<void>;
  loadModerationActions: () => Promise<void>;
  loadModerationAppeals: () => Promise<void>;
  recheckSuspension: () => Promise<void>;
  loadEmail: () => Promise<void>;
  saveEmail: (email: string | null) => Promise<void>;
  loadRating: (formatId: string) => Promise<MyRating | null>;
  refreshCore: () => Promise<void>;
  formatForName: (name: string) => string | null;
  primaryFormatId: string | null;
};

const AppContext = createContext<AppValue | null>(null);

const initialAuth: AuthState = {
  purpose: 'registration',
  phone: '',
  email: '',
  challengeId: null,
  verifiedChallengeId: null,
};

const initialOnboarding: OnboardingState = {
  formats: [],
  level: 'intermediate',
  courtPreference: 'ANY',
  windows: [],
  displayName: '',
  avatar: { skin: '#A6ABB1', hair: '#383D43', shirt: '#62686E', style: 2, glasses: false },
};

export function AppProvider({ children }: PropsWithChildren) {
  const [ready, setReady] = useState(false);
  const [hydratedToken, setHydratedToken] = useState<string | null>(null);
  const [session, setSessionState] = useState<Session | null>(null);
  const sessionRef = useRef<Session | null>(null);
  const [dark, setDark] = useState(() => Appearance.getColorScheme() === 'dark');
  const [auth, setAuthState] = useState<AuthState>(initialAuth);
  const [onboarding, setOnboardingState] = useState<OnboardingState>(initialOnboarding);
  const [catalog, setCatalog] = useState<Sport[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [track, setTrack] = useState<Track | null>(null);
  const [badges, setBadges] = useState<Badge[]>([]);
  const [missions, setMissions] = useState<Mission[]>([]);
  const [matches, setMatches] = useState<MatchSummary[]>([]);
  const [queue, setQueue] = useState<QueueEntry | null>(null);
  const [ratings, setRatings] = useState<Record<string, MyRating>>({});
  const [packs, setPacks] = useState<TicketPack[]>([]);
  const [pass, setPass] = useState<PassSubscription | null>(null);
  const [passPlans, setPassPlans] = useState<PassPlan[]>([]);
  const [bands, setBands] = useState<Band[]>([]);
  const [venues, setVenues] = useState<Venue[]>([]);
  const [friends, setFriends] = useState<Friend[]>([]);
  const [invites, setInvites] = useState<LobbyInvite[]>([]);
  const [clan, setClan] = useState<Clan | null>(null);
  const [clanMembers, setClanMembers] = useState<ClanMember[]>([]);
  const [clanMessages, setClanMessages] = useState<ClanMessage[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [network, setNetwork] = useState<Network | null>(null);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const [suspended, setSuspended] = useState(false);
  const [moderationActions, setModerationActions] = useState<ModerationAction[]>([]);
  const [moderationAppeals, setModerationAppeals] = useState<ModerationAppeal[]>([]);
  const [email, setEmail] = useState<string | null>(null);
  const [emailReady, setEmailReady] = useState(false);
  const [accessibility, setAccessibilityState] =
    useState<AccessibilityPreferences>(defaultAccessibility);

  const token = session?.accessToken ?? null;

  const setSession = useCallback(async (tokens: Parameters<typeof saveSession>[0]) => {
    const stored = await saveSession(tokens);
    sessionRef.current = stored;
    setSuspended(false);
    setSessionState(stored);
  }, []);

  const signOut = useCallback(async () => {
    if (token) {
      try {
        await api.auth.logout(token);
      } catch {
        // A sessao local e encerrada mesmo se o servidor nao responder.
      }
    }
    await clearSession();
    sessionRef.current = null;
    setSessionState(null);
    setProfile(null);
    setWallet(null);
    setProgress(null);
    setTrack(null);
    setBadges([]);
    setMissions([]);
    setMatches([]);
    setQueue(null);
    setRatings({});
    setPacks([]);
    setPass(null);
    setPassPlans([]);
    setVenues([]);
    setFriends([]);
    setInvites([]);
    setClan(null);
    setClanMembers([]);
    setClanMessages([]);
    setStats(null);
    setNetwork(null);
    setBookings([]);
    setNotifications([]);
    setUnreadNotifications(0);
    setSuspended(false);
    setModerationActions([]);
    setModerationAppeals([]);
    setEmail(null);
    setEmailReady(false);
    setAuthState(initialAuth);
    setOnboardingState(initialOnboarding);
  }, [token]);

  const setAuth = useCallback((patch: Partial<AuthState>) => {
    setAuthState((current) => ({ ...current, ...patch }));
  }, []);

  const setOnboarding = useCallback((patch: Partial<OnboardingState>) => {
    setOnboardingState((current) => ({ ...current, ...patch }));
  }, []);

  const loadCatalog = useCallback(async () => {
    const result = await api.profile.catalog();
    setCatalog(result.sports);
    return result.sports;
  }, []);

  const loadProfile = useCallback(async () => {
    if (!token) {
      return null;
    }
    const result = await api.profile.me(token);
    setProfile(result);
    return result;
  }, [token]);

  const loadWallet = useCallback(async () => {
    if (!token) {
      return null;
    }
    const result = await api.tickets.wallet(token);
    setWallet(result);
    return result;
  }, [token]);

  const loadSeason = useCallback(async () => {
    if (!token) {
      return;
    }
    const [progressResult, trackResult, badgeResult, missionResult] = await Promise.all([
      api.progress.get(token),
      api.progress.track(token),
      api.progress.badges(token),
      api.progress.missions(token),
    ]);
    setProgress(progressResult);
    setTrack(trackResult);
    setBadges(badgeResult.badges);
    setMissions(missionResult.missions);
  }, [token]);

  const loadMatches = useCallback(async () => {
    if (!token) {
      return [];
    }
    const result = await api.matches.list(token);
    setMatches(result.matches);
    return result.matches;
  }, [token]);

  const loadQueue = useCallback(async () => {
    if (!token) {
      return null;
    }
    const result = await api.matchmaking.state(token);
    setQueue(result.entry);
    return result.entry;
  }, [token]);

  const loadStore = useCallback(async () => {
    if (!token) {
      return;
    }
    const [packResult, bandResult, passPlansResult, passResult] = await Promise.all([
      api.tickets.packs(token),
      api.pricing.bands(token),
      api.passes.plans(token),
      api.passes.get(token),
    ]);
    setPacks(packResult.packs);
    setBands(bandResult.bands);
    setPassPlans(passPlansResult.plans);
    setPass(passResult.subscription);
  }, [token]);

  const loadPass = useCallback(async () => {
    if (!token) {
      return;
    }
    const [plans, current] = await Promise.all([api.passes.plans(token), api.passes.get(token)]);
    setPassPlans(plans.plans);
    setPass(current.subscription);
  }, [token]);

  const loadSocial = useCallback(async () => {
    if (!token) {
      return;
    }
    const [friendResult, inviteResult] = await Promise.all([
      api.social.friends(token),
      api.social.invites(token),
    ]);
    setFriends(friendResult.friends);
    setInvites(inviteResult.invites);
  }, [token]);

  const loadClan = useCallback(async () => {
    if (!token) {
      return;
    }
    const current = await api.clans.mine(token);
    setClan(current);
    if (current) {
      const [memberResult, messageResult] = await Promise.all([
        api.clans.members(token, current.id),
        api.clans.messages(token, current.id),
      ]);
      setClanMembers(memberResult.members);
      setClanMessages(messageResult.messages);
    } else {
      setClanMembers([]);
      setClanMessages([]);
    }
  }, [token]);

  const loadClanMessages = useCallback(
    async (clanId: string) => {
      if (!token) {
        return [];
      }
      const result = await api.clans.messages(token, clanId);
      setClanMessages(result.messages);
      return result.messages;
    },
    [token],
  );

  const loadStats = useCallback(async () => {
    if (!token) {
      return;
    }
    const [statsResult, networkResult] = await Promise.all([
      api.stats.me(token),
      api.stats.network(token),
    ]);
    setStats(statsResult);
    setNetwork(networkResult);
  }, [token]);

  const loadVenues = useCallback(async () => {
    if (!token) {
      return [];
    }
    const result = await api.profile.venues(token);
    setVenues(result.items);
    return result.items;
  }, [token]);

  const loadBookings = useCallback(async () => {
    if (!token) {
      return [];
    }
    const result = await api.bookings.list(token);
    setBookings(result.bookings);
    return result.bookings;
  }, [token]);

  const loadNotifications = useCallback(async () => {
    if (!token) {
      return;
    }
    const result = await api.notifications.list(token);
    setNotifications(result.notifications);
    setUnreadNotifications(result.unread_count);
  }, [token]);

  const markNotificationRead = useCallback(
    async (notificationId: string) => {
      if (!token) {
        return;
      }
      const wasUnread = notifications.some((item) => item.id === notificationId && !item.read_at);
      const updated = await api.notifications.markRead(token, notificationId);
      setNotifications((current) =>
        current.map((item) => (item.id === notificationId ? updated : item)),
      );
      if (wasUnread) {
        setUnreadNotifications((current) => Math.max(0, current - 1));
      }
    },
    [token, notifications],
  );

  const markAllNotificationsRead = useCallback(async () => {
    if (!token) {
      return;
    }
    await api.notifications.markAllRead(token);
    setNotifications((current) =>
      current.map((item) => ({
        ...item,
        read_at: item.read_at ?? new Date().toISOString(),
      })),
    );
    setUnreadNotifications(0);
  }, [token]);

  const loadModerationActions = useCallback(async () => {
    if (!token) {
      return;
    }
    const result = await api.moderation.listMyActions(token);
    setModerationActions(result.actions);
  }, [token]);

  const loadModerationAppeals = useCallback(async () => {
    if (!token) {
      return;
    }
    const result = await api.moderation.listMyAppeals(token);
    setModerationAppeals(result.appeals);
  }, [token]);

  const loadEmail = useCallback(async () => {
    if (!token) {
      setEmail(null);
      setEmailReady(true);
      return;
    }
    try {
      const result = await api.profile.email(token);
      setEmail(result.email);
    } finally {
      setEmailReady(true);
    }
  }, [token]);

  const saveEmail = useCallback(
    async (value: string | null) => {
      if (!token) {
        return;
      }
      const result = await api.profile.updateEmail(token, value?.trim() || null);
      setEmail(result.email);
      setEmailReady(true);
    },
    [token],
  );

  const loadRating = useCallback(
    async (formatId: string) => {
      if (!token) {
        return null;
      }
      const result = await api.ratings.me(token, formatId);
      setRatings((current) => ({ ...current, [formatId]: result }));
      return result;
    },
    [token],
  );

  const refreshCore = useCallback(async () => {
    if (!token) {
      return;
    }
    await Promise.allSettled([
      loadProfile(),
      loadWallet(),
      loadMatches(),
      loadQueue(),
      loadSeason(),
      loadNotifications(),
      loadModerationActions(),
      loadEmail(),
    ]);
    if (catalog.length === 0) {
      await loadCatalog().catch(() => []);
    }
  }, [
    token,
    loadProfile,
    loadWallet,
    loadMatches,
    loadQueue,
    loadSeason,
    loadNotifications,
    loadModerationActions,
    loadEmail,
    catalog.length,
    loadCatalog,
  ]);

  const recheckSuspension = useCallback(async () => {
    if (!token) {
      return;
    }
    await Promise.allSettled([loadModerationActions(), loadModerationAppeals()]);
    try {
      const current = sessionRef.current;
      if (!current) {
        return;
      }
      await api.auth.me(current.accessToken);
      setSuspended(false);
      const after = sessionRef.current;
      if (after && after.accessToken !== current.accessToken) {
        // O refresh já trocou os tokens; o efeito de token recarrega os dados.
        return;
      }
      await refreshCore();
    } catch {
      // A conta continua suspensa ou a rede falhou; a tela permanece.
    }
  }, [token, refreshCore, loadModerationActions, loadModerationAppeals]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const stored = await loadSession();
        if (stored) {
          try {
            let current = stored;
            if (
              stored.accessExpiresAt &&
              new Date(stored.accessExpiresAt).getTime() < Date.now() + 30_000
            ) {
              current = await refreshStoredSession(stored);
            }
            if (active) {
              sessionRef.current = current;
              setSessionState(current);
              setSuspended(current.userStatus === 'suspended');
            }
          } catch (error) {
            if (error instanceof ApiError && error.code === 'account_suspended') {
              // Fallback para servidor antigo: preserva a sessão e abre a tela de suspensão.
              if (active) {
                sessionRef.current = stored;
                setSessionState(stored);
                setSuspended(true);
              }
            } else if (error instanceof ApiError && error.status === 401) {
              // Apenas credencial inválida encerra a sessão.
              sessionRef.current = null;
              await clearSession();
            } else {
              // Rede indisponível no cold start: mantém a sessão salva e abre o app.
              if (active) {
                sessionRef.current = stored;
                setSessionState(stored);
                setSuspended(stored.userStatus === 'suspended');
              }
            }
          }
        }
      } finally {
        if (active) {
          setReady(true);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    loadAccessibility().then((preferences) => {
      if (active) {
        setAccessibilityState(preferences);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const setAccessibility = useCallback(async (preferences: AccessibilityPreferences) => {
    setAccessibilityState(preferences);
    await saveAccessibility(preferences);
  }, []);

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  useEffect(() => {
    if (!token) {
      setRefreshHandler(null);
      return;
    }
    setRefreshHandler(async () => {
      const current = sessionRef.current;
      if (!current) {
        return null;
      }
      try {
        const refreshed = await refreshStoredSession(current);
        sessionRef.current = refreshed;
        setSessionState(refreshed);
        setSuspended(refreshed.userStatus === 'suspended');
        return refreshed.accessToken;
      } catch (error) {
        if (error instanceof ApiError && error.code === 'account_suspended') {
          setSuspended(true);
          return null;
        }
        if (error instanceof ApiError && error.status === 401) {
          sessionRef.current = null;
          await clearSession();
          setSessionState(null);
        }
        return null;
      }
    });
    return () => setRefreshHandler(null);
  }, [token]);

  useEffect(() => {
    setSuspensionHandler(() => {
      setSuspended(true);
    });
    return () => setSuspensionHandler(null);
  }, []);

  useEffect(() => {
    if (!token) {
      stopRealtime();
      return;
    }
    startRealtime(token);
    const unsubscribe = subscribeRealtime((event) => {
      if (event.type === 'lobby.invite.created') {
        loadNotifications().catch(() => undefined);
      }
    });
    return () => {
      unsubscribe();
      stopRealtime();
    };
  }, [token, loadNotifications]);

  useEffect(() => {
    if (!token) {
      return;
    }
    if (sessionRef.current?.userStatus === 'suspended') {
      // Nao chama as rotas normais: elas respondem 401 enquanto a conta estiver suspensa.
      setSuspended(true);
      setHydratedToken(token);
      return;
    }
    // Carga inicial e sincronizacao de sessao: chamadas assincronas atualizam o estado.
    refreshCore()
      .catch(() => undefined)
      .finally(() => setHydratedToken(token));
    loadCatalog().catch(() => undefined);
  }, [token, refreshCore, loadCatalog]);

  const formatForName = useCallback(
    (name: string) => {
      const target = name.toLowerCase();
      for (const sport of catalog) {
        for (const format of sport.formats) {
          if (format.name.toLowerCase() === target) {
            return format.id;
          }
          if (
            target.includes(format.name.toLowerCase()) ||
            format.name.toLowerCase().includes(target)
          ) {
            return format.id;
          }
        }
      }
      return null;
    },
    [catalog],
  );

  const primaryFormatId = useMemo(() => {
    if (profile?.sports.length) {
      return profile.sports[0].format_id;
    }
    for (const sport of catalog) {
      if (sport.formats.length) {
        return sport.formats[0].id;
      }
    }
    return null;
  }, [profile, catalog]);

  const hydrated = !token || hydratedToken === token;

  const value = useMemo<AppValue>(
    () => ({
      ready,
      hydrated,
      session,
      dark,
      setDark,
      auth,
      setAuth,
      onboarding,
      setOnboarding,
      catalog,
      profile,
      wallet,
      progress,
      track,
      badges,
      missions,
      matches,
      queue,
      ratings,
      packs,
      pass,
      passPlans,
      bands,
      venues,
      friends,
      invites,
      clan,
      clanMembers,
      clanMessages,
      stats,
      network,
      bookings,
      notifications,
      unreadNotifications,
      suspended,
      moderationActions,
      moderationAppeals,
      email,
      emailReady,
      accessibility,
      setAccessibility,
      setSession,
      signOut,
      setProfile,
      setPass,
      setClan,
      setMatches,
      setQueue,
      loadCatalog,
      loadProfile,
      loadWallet,
      loadSeason,
      loadMatches,
      loadQueue,
      loadStore,
      loadPass,
      loadSocial,
      loadClan,
      loadClanMessages,
      loadStats,
      loadVenues,
      loadBookings,
      loadNotifications,
      markNotificationRead,
      markAllNotificationsRead,
      loadModerationActions,
      loadModerationAppeals,
      loadEmail,
      saveEmail,
      recheckSuspension,
      loadRating,
      refreshCore,
      formatForName,
      primaryFormatId,
    }),
    [
      ready,
      hydrated,
      session,
      dark,
      auth,
      setAuth,
      onboarding,
      setOnboarding,
      catalog,
      profile,
      wallet,
      progress,
      track,
      badges,
      missions,
      matches,
      queue,
      ratings,
      packs,
      pass,
      passPlans,
      bands,
      venues,
      friends,
      invites,
      clan,
      clanMembers,
      clanMessages,
      stats,
      network,
      bookings,
      notifications,
      unreadNotifications,
      suspended,
      moderationActions,
      moderationAppeals,
      email,
      emailReady,
      accessibility,
      setAccessibility,
      setSession,
      signOut,
      loadCatalog,
      loadProfile,
      loadWallet,
      loadSeason,
      loadMatches,
      loadQueue,
      loadStore,
      loadPass,
      loadSocial,
      loadClan,
      loadClanMessages,
      loadStats,
      loadVenues,
      loadBookings,
      loadNotifications,
      markNotificationRead,
      markAllNotificationsRead,
      loadModerationActions,
      loadModerationAppeals,
      loadEmail,
      saveEmail,
      recheckSuspension,
      loadRating,
      refreshCore,
      formatForName,
      primaryFormatId,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppValue {
  const value = useContext(AppContext);
  if (!value) {
    throw new Error('useApp fora do provider');
  }
  return value;
}
