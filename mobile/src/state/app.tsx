import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from 'react';
import { AppState, Appearance } from 'react-native';

import {
  api,
  ApiError,
  setCurrentTokenProvider,
  setRefreshHandler,
  setSessionExpiredHandler,
  setSuspensionHandler,
  setUpdateRequiredHandler,
  type RefreshResult,
} from '../api/client';
import { startRealtime, stopRealtime, subscribeRealtime } from '../api/realtime';
import { classifyRefreshFailure } from '../api/refreshPolicy';
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
  FriendRequest,
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
  QueueCourtPreference,
  QueueSelectionPayload,
  Sport,
  Stats,
  TicketPack,
  Track,
  Wallet,
  Venue,
  VisualCatalog,
  VisualIdentity,
  VisualIdentityResponse,
} from '../api/types';
import {
  clearSession,
  loadSession,
  refreshSession,
  refreshStoredSession,
  saveSession,
  type Session,
} from '../session';
import {
  DEFAULT_IDENTITY,
  LOCAL_VISUAL_CATALOG,
  normalizeIdentity,
  visualUpdatePayload,
} from '../ui/identity';
import {
  applyNetworkFailure,
  cancelOutcome,
  emptySnapshot,
  formatLabelFromCatalog,
  isCourtPreference,
  isExpired,
  isNetworkFailure,
  isStaleRevision,
  itemsToPairs,
  reconcileEntries,
  selectionItemsError,
  snapshotCoversPairs,
  snapshotFromEntries,
  type QueueCancelOutcome,
  type QueueReplaceOutcome,
  type QueueSnapshot,
} from './queueState';
import { useQueueWatcher } from './queueWatcher';

export type OnboardingState = {
  formats: string[];
  level: string;
  courtPreference: string;
  windows: Availability[];
  displayName: string;
  visual: VisualIdentity;
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
  /** Entradas `waiting` confirmadas pelo servidor (contrato 0057). */
  queue: QueueEntry[];
  /** Entrada `matched` devolvida no campo legado `entry`. */
  matchedEntry: QueueEntry | null;
  queueReconnecting: boolean;
  queueNotice: string | null;
  ratings: Record<string, MyRating>;
  packs: TicketPack[];
  pass: PassSubscription | null;
  passPlans: PassPlan[];
  bands: Band[];
  venues: Venue[];
  friends: Friend[];
  friendRequestsIncoming: FriendRequest[];
  friendRequestsOutgoing: FriendRequest[];
  blocks: Friend[];
  /** Seções sociais que falharam na última carga (`friends`, `incoming`...). */
  socialFailures: string[];
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
  updateRequired: boolean;
  moderationActions: ModerationAction[];
  moderationAppeals: ModerationAppeal[];
  email: string | null;
  emailReady: boolean;
  accessibility: AccessibilityPreferences;
  visual: VisualIdentity;
  visualCatalog: VisualCatalog;
  setAccessibility: (preferences: AccessibilityPreferences) => Promise<void>;
  setSession: (tokens: Parameters<typeof saveSession>[0]) => Promise<void>;
  signOut: () => Promise<void>;
  setProfile: (profile: Profile | null) => void;
  setPass: (pass: PassSubscription | null) => void;
  setClan: (clan: Clan | null) => void;
  setMatches: (matches: MatchSummary[]) => void;
  setQueue: (entries: QueueEntry[], matched?: QueueEntry | null) => void;
  loadCatalog: () => Promise<Sport[]>;
  loadProfile: () => Promise<Profile | null>;
  loadWallet: () => Promise<Wallet | null>;
  loadSeason: () => Promise<void>;
  loadMatches: () => Promise<MatchSummary[]>;
  loadQueue: () => Promise<QueueSnapshot | null>;
  /** Um único `PUT` com `selections` explícitas (pares, sem produto cartesiano). */
  replaceQueue: (payload: QueueSelectionPayload) => Promise<QueueReplaceOutcome>;
  cancelQueue: () => Promise<QueueCancelOutcome>;
  clearQueueNotice: () => void;
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
  loadVisual: () => Promise<void>;
  saveVisual: (
    patch: Partial<VisualIdentity>,
  ) => Promise<{ identity: VisualIdentity; synced: boolean; error?: string }>;
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
  visual: DEFAULT_IDENTITY,
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
  const [queue, setQueueState] = useState<QueueEntry[]>([]);
  const [matchedEntry, setMatchedEntry] = useState<QueueEntry | null>(null);
  const [queueReconnecting, setQueueReconnecting] = useState(false);
  const [queueNotice, setQueueNotice] = useState<string | null>(null);
  const [ratings, setRatings] = useState<Record<string, MyRating>>({});
  const [packs, setPacks] = useState<TicketPack[]>([]);
  const [pass, setPass] = useState<PassSubscription | null>(null);
  const [passPlans, setPassPlans] = useState<PassPlan[]>([]);
  const [bands, setBands] = useState<Band[]>([]);
  const [venues, setVenues] = useState<Venue[]>([]);
  const [friends, setFriends] = useState<Friend[]>([]);
  const [friendRequestsIncoming, setFriendRequestsIncoming] = useState<FriendRequest[]>([]);
  const [friendRequestsOutgoing, setFriendRequestsOutgoing] = useState<FriendRequest[]>([]);
  const [blocks, setBlocks] = useState<Friend[]>([]);
  const [socialFailures, setSocialFailures] = useState<string[]>([]);
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
  const [updateRequired, setUpdateRequired] = useState(false);
  const [moderationActions, setModerationActions] = useState<ModerationAction[]>([]);
  const [moderationAppeals, setModerationAppeals] = useState<ModerationAppeal[]>([]);
  const [email, setEmail] = useState<string | null>(null);
  const [emailReady, setEmailReady] = useState(false);
  const [accessibility, setAccessibilityState] =
    useState<AccessibilityPreferences>(defaultAccessibility);
  const [visual, setVisual] = useState<VisualIdentity>(DEFAULT_IDENTITY);
  const [visualCatalog, setVisualCatalog] = useState<VisualCatalog>(LOCAL_VISUAL_CATALOG);
  /** Chaves confirmadas por `GET /me/visual`; autoridade para o próximo PUT. */
  const [confirmedVisual, setConfirmedVisual] = useState<VisualIdentityResponse | null>(null);
  const queueSnapshotRef = useRef<QueueSnapshot>(emptySnapshot());
  const queueRevisionRef = useRef(0);
  const socialRevisionRef = useRef(0);

  const token = session?.accessToken ?? null;

  /**
   * Ponto único de aplicação do estado da fila. A UI nunca deriva entradas da
   * seleção local: só deste snapshot vindo do servidor.
   */
  const commitQueueSnapshot = useCallback(
    (snapshot: QueueSnapshot, announceExpired = false) => {
      const previous = queueSnapshotRef.current;
      const present = new Set(snapshot.entries.map((entry) => entry.id));
      if (snapshot.matched) {
        present.add(snapshot.matched.id);
      }
      const vanished = previous.entries.filter(
        (entry) => !present.has(entry.id) && isExpired(entry, Date.now()),
      );
      const expired = [...snapshot.expired, ...vanished].filter(
        (entry, index, all) => all.findIndex((item) => item.id === entry.id) === index,
      );
      if (announceExpired && expired.length > 0) {
        const names = Array.from(
          new Set(expired.map((entry) => formatLabelFromCatalog(catalog, entry.format_id))),
        );
        setQueueNotice(
          names.length === 1
            ? `Sua busca por ${names[0]} expirou. Você pode buscar de novo quando quiser.`
            : `${names.length} buscas expiraram. Você pode buscar de novo quando quiser.`,
        );
      }
      queueSnapshotRef.current = snapshot;
      setQueueState(snapshot.entries);
      setMatchedEntry(snapshot.matched);
    },
    [catalog],
  );

  const setQueue = useCallback(
    (entries: QueueEntry[], matched: QueueEntry | null = null) => {
      queueRevisionRef.current += 1;
      commitQueueSnapshot(snapshotFromEntries(entries, matched));
    },
    [commitQueueSnapshot],
  );

  const loadQueue = useCallback(async (): Promise<QueueSnapshot | null> => {
    if (!token) {
      commitQueueSnapshot(emptySnapshot());
      return null;
    }
    const revision = queueRevisionRef.current;
    const response = await api.queue.state(token);
    // Uma resposta de poll iniciada antes de `PUT`/`DELETE` não pode repor
    // entradas antigas nem reabrir a busca.
    if (isStaleRevision(revision, queueRevisionRef.current)) {
      return queueSnapshotRef.current;
    }
    const snapshot = reconcileEntries(response, Date.now());
    commitQueueSnapshot(snapshot, true);
    return snapshot;
  }, [token, commitQueueSnapshot]);

  const replaceQueue = useCallback(
    async (payload: QueueSelectionPayload): Promise<QueueReplaceOutcome> => {
      if (!token) {
        return {
          ok: false,
          code: 'unauthenticated',
          snapshot: queueSnapshotRef.current,
          reconciled: false,
        };
      }
      if (selectionItemsError(payload.selections)) {
        return {
          ok: false,
          code: 'invalid_selection',
          snapshot: queueSnapshotRef.current,
          reconciled: false,
        };
      }
      queueRevisionRef.current += 1;
      const revision = queueRevisionRef.current;
      setQueueNotice(null);
      // O PUT grava a quadra efetiva no perfil de cada formato (ADR 0067).
      // Refletimos em memória o que o servidor devolveu, sem PUT de perfil.
      const applyServerCourts = (snapshot: QueueSnapshot) => {
        const courts = new Map<string, QueueCourtPreference>();
        for (const entry of [
          ...snapshot.entries,
          ...(snapshot.matched ? [snapshot.matched] : []),
        ]) {
          if (isCourtPreference(entry.court_preference)) {
            courts.set(entry.format_id, entry.court_preference);
          }
        }
        if (courts.size === 0) {
          return;
        }
        setProfile((current) => {
          if (!current) {
            return current;
          }
          let changed = false;
          const sports = current.sports.map((sport) => {
            const court = courts.get(sport.format_id);
            if (!court || sport.court_preference === court) {
              return sport;
            }
            changed = true;
            return { ...sport, court_preference: court };
          });
          return changed ? { ...current, sports } : current;
        });
      };
      try {
        // Uma única chamada atômica com os pares explícitos. Sem `formats`,
        // `modes` ou `levels`: são mutuamente exclusivos com `selections`.
        const response = await api.queue.replace(token, payload);
        const snapshot = reconcileEntries(response, Date.now());
        if (revision === queueRevisionRef.current) {
          commitQueueSnapshot(snapshot);
          applyServerCourts(snapshot);
        }
        // Invalida GETs que começaram durante o PUT: eles podem trazer o
        // estado antigo e não podem repor a fila depois da substituição.
        queueRevisionRef.current += 1;
        return { ok: true, snapshot, reconciled: false };
      } catch (caught) {
        const apiError = caught instanceof ApiError ? caught : null;
        const code = apiError?.code ?? 'request_failed';
        const networkFailure = isNetworkFailure(apiError?.status ?? 0, code);
        if (networkFailure) {
          // O PUT pode ter commitado; nunca desfazemos no cliente. Relemos.
          try {
            const reloaded = await api.queue.state(token);
            if (isStaleRevision(revision, queueRevisionRef.current)) {
              return {
                ok: false,
                code,
                snapshot: queueSnapshotRef.current,
                reconciled: true,
              };
            }
            const outcome = applyNetworkFailure(queueSnapshotRef.current, reloaded, Date.now());
            commitQueueSnapshot(outcome.snapshot);
            applyServerCourts(outcome.snapshot);
            queueRevisionRef.current += 1;
            if (snapshotCoversPairs(outcome.snapshot, itemsToPairs(payload.selections))) {
              return { ok: true, snapshot: outcome.snapshot, reconciled: true };
            }
            return {
              ok: false,
              code,
              snapshot: outcome.snapshot,
              reconciled: outcome.reconciled,
            };
          } catch {
            return {
              ok: false,
              code,
              snapshot: queueSnapshotRef.current,
              reconciled: false,
            };
          }
        }
        // 4xx: o backend valida tudo antes de escrever; a seleção anterior
        // permanece. Não limpamos a lista exibida.
        return {
          ok: false,
          code,
          snapshot: queueSnapshotRef.current,
          reconciled: false,
        };
      }
    },
    [token, commitQueueSnapshot],
  );

  const cancelQueue = useCallback(async (): Promise<QueueCancelOutcome> => {
    if (!token) {
      return {
        ok: false,
        cleared: false,
        code: 'unauthenticated',
        snapshot: queueSnapshotRef.current,
      };
    }
    queueRevisionRef.current += 1;
    const revision = queueRevisionRef.current;
    try {
      await api.queue.leave(token);
      const empty = emptySnapshot();
      if (revision === queueRevisionRef.current) {
        commitQueueSnapshot(empty);
      }
      // GETs iniciados durante o DELETE não podem repor entradas canceladas.
      queueRevisionRef.current += 1;
      const confirmRevision = queueRevisionRef.current;
      setQueueNotice(null);
      // Confirmação best-effort: se falhar, o 204 já é a verdade.
      try {
        const response = await api.queue.state(token);
        if (confirmRevision === queueRevisionRef.current) {
          commitQueueSnapshot(reconcileEntries(response, Date.now()));
        }
      } catch {
        // Mantém o estado vazio confirmado pelo DELETE.
      }
      return { ok: true, cleared: true, code: null, snapshot: empty };
    } catch (caught) {
      const apiError = caught instanceof ApiError ? caught : null;
      const status = apiError?.status ?? 0;
      if (cancelOutcome(status) === 'cleared') {
        // 404 `not_queued`: já não havia fila; cancelar é idempotente.
        const empty = emptySnapshot();
        if (revision === queueRevisionRef.current) {
          commitQueueSnapshot(empty);
        }
        queueRevisionRef.current += 1;
        setQueueNotice(null);
        return { ok: true, cleared: true, code: null, snapshot: empty };
      }
      return {
        ok: false,
        cleared: false,
        code: apiError?.code ?? 'request_failed',
        snapshot: queueSnapshotRef.current,
      };
    }
  }, [token, commitQueueSnapshot]);

  const clearQueueNotice = useCallback(() => setQueueNotice(null), []);

  const setSession = useCallback(async (tokens: Parameters<typeof saveSession>[0]) => {
    const stored = await saveSession(tokens);
    sessionRef.current = stored;
    setSuspended(false);
    setSessionState(stored);
  }, []);

  /** Limpa estado local de sessão sem chamar `/auth/logout`. */
  const resetSessionState = useCallback(() => {
    sessionRef.current = null;
    setSessionState(null);
    setProfile(null);
    setWallet(null);
    setProgress(null);
    setTrack(null);
    setBadges([]);
    setMissions([]);
    setMatches([]);
    setQueue([], null);
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
    setVisual(DEFAULT_IDENTITY);
    setVisualCatalog(LOCAL_VISUAL_CATALOG);
    setConfirmedVisual(null);
    setAuthState(initialAuth);
    setOnboardingState(initialOnboarding);
  }, [setQueue]);

  const signOut = useCallback(async () => {
    if (token) {
      try {
        await api.auth.logout(token);
      } catch {
        // A sessao local e encerrada mesmo se o servidor nao responder.
      }
    }
    await clearSession();
    resetSessionState();
  }, [token, resetSessionState]);

  /**
   * Sessão inválida (401 pós-refresh que não é suspensão): o token já não vale,
   * então não chamamos `/auth/logout` — isso geraria outro 401. Limpa o estado
   * local e o `Shell` volta para a tela de entrada/login.
   */
  const expireSession = useCallback(
    (accessToken?: string | null) => {
      // Um 401 atrasado de um token antigo não pode derrubar a sessão atual.
      if (!sessionRef.current) {
        return;
      }
      if (accessToken && sessionRef.current.accessToken !== accessToken) {
        return;
      }
      if (__DEV__) {
        console.warn('[session] sessão inválida; voltando ao login sem suspensão.');
      }
      resetSessionState();
      void clearSession().catch(() => undefined);
    },
    [resetSessionState],
  );

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
    // Uma resposta antiga (boot, foreground, foco de tela) não pode sobrescrever
    // o resultado de uma recarga disparada depois de uma mutação.
    const revision = ++socialRevisionRef.current;
    // Paralelo tolerante: uma rota que falha não impede as outras de atualizar
    // a tela e não derruba as listas já carregadas. A seção afetada fica em
    // `socialFailures` para a tela avisar sem esconder o que está bom.
    const [friendResult, incomingResult, outgoingResult, blockResult, inviteResult] =
      await Promise.allSettled([
        api.social.friends(token),
        api.social.friendRequests(token, 'incoming'),
        api.social.friendRequests(token, 'outgoing'),
        api.social.blocks(token),
        api.social.invites(token),
      ]);
    if (revision !== socialRevisionRef.current) {
      return;
    }
    const failures: string[] = [];
    if (friendResult.status === 'fulfilled') {
      setFriends(friendResult.value.friends);
    } else {
      failures.push('friends');
    }
    if (incomingResult.status === 'fulfilled') {
      setFriendRequestsIncoming(incomingResult.value.requests);
    } else {
      failures.push('incoming');
    }
    if (outgoingResult.status === 'fulfilled') {
      setFriendRequestsOutgoing(outgoingResult.value.requests);
    } else {
      failures.push('outgoing');
    }
    if (blockResult.status === 'fulfilled') {
      setBlocks(blockResult.value.blocks);
    } else {
      failures.push('blocks');
    }
    if (inviteResult.status === 'fulfilled') {
      setInvites(inviteResult.value.invites);
    } else {
      failures.push('invites');
    }
    setSocialFailures(failures);
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

  const loadVisual = useCallback(async () => {
    let catalog = LOCAL_VISUAL_CATALOG;
    try {
      const remote = await api.visual.catalog();
      if (remote?.items?.length) {
        catalog = remote;
      }
    } catch (error) {
      if (__DEV__) {
        // O catálogo remoto ainda pode não existir; o fallback local mantém a UI.
        console.warn('catalog/visual indisponível, usando catálogo local', error);
      }
    }
    setVisualCatalog(catalog);
    if (!token) {
      setVisual((current) => normalizeIdentity(current, catalog));
      return;
    }
    try {
      const remoteIdentity = await api.visual.me(token);
      setConfirmedVisual(remoteIdentity);
      setVisual(normalizeIdentity(remoteIdentity, catalog));
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        // O `call` já passou pelo refresh single-flight e, se ele falhou,
        // acionou `sessionExpiredHandler`. Não trate 401 como “identidade
        // indisponível”: isso mascarava o logout e repetia o aviso.
        return;
      }
      if (__DEV__) {
        console.warn('me/visual indisponível, usando identidade padrão', error);
      }
      setVisual((current) => normalizeIdentity(current, catalog));
    }
  }, [token]);

  const saveVisual = useCallback(
    async (patch: Partial<VisualIdentity>) => {
      const next = normalizeIdentity({ ...visual, ...patch }, visualCatalog);
      setVisual(next);
      if (!token) {
        return { identity: next, synced: false };
      }
      // O PUT valida os seis slots. `entry`/`emote` não têm editor: preserva a
      // chave confirmada pelo servidor em vez de mandar o default local.
      const payload = visualUpdatePayload(next, visualCatalog, confirmedVisual);
      if (!payload) {
        return {
          identity: next,
          synced: false,
          error:
            'Catálogo de identidade do servidor indisponível. Tente novamente quando houver conexão.',
        };
      }
      try {
        const saved = await api.visual.update(token, payload);
        setConfirmedVisual(saved);
        const normalized = normalizeIdentity(saved, visualCatalog);
        setVisual(normalized);
        return { identity: normalized, synced: true };
      } catch (error) {
        if (
          error instanceof ApiError &&
          (error.code === 'visual_item_locked' || error.code === 'invalid_visual_item')
        ) {
          setVisual(visual);
          return {
            identity: visual,
            synced: false,
            error:
              error.code === 'visual_item_locked'
                ? 'Este item ainda não está liberado.'
                : 'Item de identidade inválido.',
          };
        }
        if (__DEV__) {
          console.warn('PUT /me/visual falhou; identidade mantida localmente', error);
        }
        return {
          identity: next,
          synced: false,
          error: 'Identidade salva neste aparelho. Sincronização com o servidor pendente.',
        };
      }
    },
    [token, visual, visualCatalog, confirmedVisual],
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
      loadSocial(),
      loadClan(),
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
    loadSocial,
    loadClan,
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
      await api.auth.me(current.accessToken, true);
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
        // `loadSession` já faz o refresh single-flight quando o access token
        // está perto de expirar. Só revogação explícita do refresh apaga a
        // sessão; rede/5xx/429 e `refresh_retry_required` a mantêm.
        const stored = await loadSession();
        if (stored && active) {
          sessionRef.current = stored;
          setSessionState(stored);
          setSuspended(stored.userStatus === 'suspended');
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

  // O cliente confere o token atual antes de renovar. Um 401 de um token já
  // rotacionado apenas repete a chamada com o token novo; sem isso, cada
  // requisição em voo dispara outra rotação e revoga a sessão em cascata.
  useLayoutEffect(() => {
    if (!token) {
      setCurrentTokenProvider(null);
      return;
    }
    setCurrentTokenProvider(() => sessionRef.current?.accessToken ?? null);
    return () => setCurrentTokenProvider(null);
  }, [token]);

  // Layout effect: o handler de refresh precisa existir antes de qualquer
  // efeito passivo que dispare chamadas autenticadas (ex.: `/me/visual`).
  useLayoutEffect(() => {
    if (!token) {
      setRefreshHandler(null);
      return;
    }
    setRefreshHandler(async (): Promise<RefreshResult> => {
      const current = sessionRef.current;
      if (!current) {
        return { ok: false, reason: 'expired' };
      }
      try {
        const refreshed = await refreshStoredSession(current);
        // Uma sessão nova pode ter assumido durante o refresh; nesse caso ela
        // manda, e não sobrescrevemos com um resultado antigo.
        const latest = sessionRef.current;
        if (latest && latest.refreshToken !== current.refreshToken) {
          return { ok: true, token: latest.accessToken };
        }
        sessionRef.current = refreshed;
        setSessionState(refreshed);
        if (refreshed.userStatus === 'suspended') {
          setSuspended(true);
          return { ok: false, reason: 'suspended' };
        }
        setSuspended(false);
        return { ok: true, token: refreshed.accessToken };
      } catch (error) {
        const apiError = error instanceof ApiError ? error : null;
        const reason = classifyRefreshFailure(apiError?.status ?? 0, apiError?.code);
        // Uma sessão nova pode ter assumido durante o refresh: não derrube a
        // sessão atual com o resultado de um token antigo.
        if (sessionRef.current?.refreshToken !== current.refreshToken) {
          return { ok: false, reason: 'unavailable' };
        }
        if (reason === 'suspended') {
          setSuspended(true);
        }
        return { ok: false, reason };
      }
    });
    return () => setRefreshHandler(null);
  }, [token]);

  useLayoutEffect(() => {
    setSessionExpiredHandler((accessToken) => expireSession(accessToken));
    return () => setSessionExpiredHandler(null);
  }, [expireSession]);

  useEffect(() => {
    setSuspensionHandler(() => {
      setSuspended(true);
    });
    return () => setSuspensionHandler(null);
  }, []);

  useEffect(() => {
    setUpdateRequiredHandler(() => {
      setUpdateRequired(true);
    });
    return () => setUpdateRequiredHandler(null);
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
    loadVisual().catch(() => undefined);
  }, [token, refreshCore, loadCatalog, loadVisual]);

  const pollQueue = useCallback(async () => {
    try {
      await loadQueue();
      setQueueReconnecting(false);
    } catch (cause) {
      setQueueReconnecting(true);
      throw cause;
    }
  }, [loadQueue]);

  // Um único poller global: ativo enquanto houver entradas `waiting`; pausa em
  // segundo plano e faz poll imediato ao voltar. Para quando a fila zera ou
  // quando uma entrada encontra partida.
  useQueueWatcher(pollQueue, !!token && queue.length > 0);

  useEffect(() => {
    if (!token || queue.length > 0) {
      return;
    }
    // Sem entradas ativas o watcher fica desligado; o foreground ainda
    // reconcilia para descobrir partida encontrada/estado externo.
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') {
        loadQueue().catch(() => undefined);
      }
    });
    return () => subscription.remove();
  }, [token, queue.length, loadQueue]);

  // Refresh oportunista no foreground: uma única tentativa, serializada pelo
  // mesmo single-flight de `session.ts` (nunca dois POSTs para o mesmo token).
  // Só roda quando o access token está perto de expirar; token válido não gira.
  useEffect(() => {
    if (!token) {
      return;
    }
    const subscription = AppState.addEventListener('change', (state) => {
      if (state !== 'active') {
        return;
      }
      const current = sessionRef.current;
      if (!current) {
        return;
      }
      const expiresAt = Date.parse(current.accessExpiresAt);
      if (Number.isFinite(expiresAt) && expiresAt > Date.now() + 60_000) {
        return;
      }
      refreshSession(current)
        .then((refreshed) => {
          if (sessionRef.current?.refreshToken !== current.refreshToken) {
            return;
          }
          sessionRef.current = refreshed;
          setSessionState(refreshed);
          setSuspended(refreshed.userStatus === 'suspended');
        })
        .catch((error) => {
          if (sessionRef.current?.refreshToken !== current.refreshToken) {
            return;
          }
          const apiError = error instanceof ApiError ? error : null;
          const reason = classifyRefreshFailure(apiError?.status ?? 0, apiError?.code);
          if (reason === 'suspended') {
            setSuspended(true);
          } else if (reason === 'expired') {
            expireSession(current.accessToken);
          }
          // `unavailable` e `retry` mantêm a sessão; a próxima chamada tenta
          // de novo e a tela mostra erro de conexão.
        });
    });
    return () => subscription.remove();
  }, [token, expireSession]);

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
      matchedEntry,
      queueReconnecting: queueReconnecting && queue.length > 0,
      queueNotice,
      ratings,
      packs,
      pass,
      passPlans,
      bands,
      venues,
      friends,
      friendRequestsIncoming,
      friendRequestsOutgoing,
      blocks,
      socialFailures,
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
      updateRequired,
      moderationActions,
      moderationAppeals,
      email,
      emailReady,
      accessibility,
      visual,
      visualCatalog,
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
      replaceQueue,
      cancelQueue,
      clearQueueNotice,
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
      loadVisual,
      saveVisual,
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
      matchedEntry,
      queueReconnecting,
      queueNotice,
      ratings,
      packs,
      pass,
      passPlans,
      bands,
      venues,
      friends,
      friendRequestsIncoming,
      friendRequestsOutgoing,
      blocks,
      socialFailures,
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
      updateRequired,
      moderationActions,
      moderationAppeals,
      email,
      emailReady,
      accessibility,
      visual,
      visualCatalog,
      setAccessibility,
      setSession,
      signOut,
      setQueue,
      loadCatalog,
      loadProfile,
      loadWallet,
      loadSeason,
      loadMatches,
      loadQueue,
      replaceQueue,
      cancelQueue,
      clearQueueNotice,
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
      loadVisual,
      saveVisual,
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
