import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { ErrorNotice, SkeletonList } from "../components/Feedback";
import { MapPinIcon } from "../components/ui/Icons";
import { Breadcrumbs, PageHeader } from "../components/ui/PageHeader";
import { Tabs } from "../components/ui/Tabs";
import { tabId, tabPanelId } from "../components/ui/tab-ids";
import { api } from "../lib/api";
import { formatError, requestIdOf, roleLabel } from "../lib/format";
import { queryKeys } from "../lib/query";
import { useDocumentTitle } from "../lib/useDocumentTitle";
import { PhotosPanel } from "./venue/PhotosPanel";
import { SpacesPanel } from "./venue/SpacesPanel";

type Tab = "spaces" | "photos";

export function VenuePage() {
  const { organizationId = "", venueId = "" } = useParams<{
    organizationId: string;
    venueId: string;
  }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const organizationQuery = useQuery({
    queryKey: queryKeys.organization(organizationId),
    queryFn: () => api.getOrganization(organizationId),
    enabled: organizationId.length > 0,
  });
  const venueQuery = useQuery({
    queryKey: queryKeys.venue(organizationId, venueId),
    queryFn: () => api.getVenue(organizationId, venueId),
    enabled: organizationId.length > 0 && venueId.length > 0,
  });
  const spacesQuery = useQuery({
    queryKey: queryKeys.spaces(organizationId, venueId),
    queryFn: async () => (await api.listSpaces(organizationId, venueId)).spaces,
    enabled: organizationId.length > 0 && venueId.length > 0,
  });
  const sportsQuery = useQuery({
    queryKey: queryKeys.sports,
    queryFn: async () => (await api.listSports()).sports,
  });
  const bandsQuery = useQuery({
    queryKey: queryKeys.bands,
    queryFn: async () => (await api.listBands()).bands,
  });
  const photosQuery = useQuery({
    queryKey: queryKeys.photos(organizationId, venueId),
    queryFn: () => api.listPhotos(organizationId, venueId),
    enabled: organizationId.length > 0 && venueId.length > 0,
  });

  const organization = organizationQuery.data;
  const venue = venueQuery.data;
  const spaces = useMemo(() => spacesQuery.data ?? [], [spacesQuery.data]);
  const requestedTab = searchParams.get("tab");
  const tab: Tab = requestedTab === "photos" ? "photos" : "spaces";
  const requestedSpace = searchParams.get("space");
  const selectedSpaceId =
    requestedSpace && spaces.some((space) => space.id === requestedSpace)
      ? requestedSpace
      : (spaces[0]?.id ?? null);

  useDocumentTitle(venue?.name ?? "Estabelecimento");

  function setTab(next: Tab) {
    const params = new URLSearchParams(searchParams);
    params.set("tab", next);
    setSearchParams(params);
  }

  function selectSpace(spaceId: string) {
    const params = new URLSearchParams(searchParams);
    params.set("space", spaceId);
    params.set("tab", "spaces");
    setSearchParams(params);
  }

  const loading =
    organizationQuery.isPending ||
    venueQuery.isPending ||
    spacesQuery.isPending ||
    sportsQuery.isPending;
  const error =
    organizationQuery.error ?? venueQuery.error ?? spacesQuery.error ?? sportsQuery.error;

  if (loading) {
    return <SkeletonList rows={4} label="Carregando quadras e agenda..." />;
  }

  if (error || !organization || !venue) {
    return (
      <>
        <ErrorNotice
          message={error ? formatError(error) : "Estabelecimento não encontrado."}
          requestId={requestIdOf(error)}
          onRetry={() => {
            void organizationQuery.refetch();
            void venueQuery.refetch();
            void spacesQuery.refetch();
          }}
        />
        <Link className="button button--link" to={`/organizations/${organizationId}`}>
          Voltar para a organização
        </Link>
      </>
    );
  }

  const photos = photosQuery.data?.photos ?? [];
  const canReview = photosQuery.data?.can_review ?? false;

  return (
    <>
      <Breadcrumbs
        items={[
          { label: "Organizações", to: "/" },
          { label: organization.name, to: `/organizations/${organization.id}` },
          { label: venue.name },
        ]}
      />

      <PageHeader
        eyebrow={roleLabel(organization.role)}
        title={venue.name}
        description={
          <>
            <span
              className={venue.status === "active" ? "badge badge--success" : "badge badge--muted"}
            >
              {venue.status === "active" ? "Ativo" : "Inativo"}
            </span>{" "}
            <span className="inline-meta">
              <MapPinIcon size={15} />
              {[venue.city, venue.state].filter(Boolean).join(" · ") || "Local não informado"}
              {venue.address_line ? ` · ${venue.address_line}` : ""}
            </span>{" "}
            · Fuso {venue.timezone}
          </>
        }
      />

      <Tabs
        items={[
          { id: "spaces", label: "Quadras e agenda", count: spaces.length },
          { id: "photos", label: "Fotos", count: photos.length },
        ]}
        active={tab}
        onChange={(id) => setTab(id as Tab)}
        idBase="venue"
        ariaLabel="Seções do estabelecimento"
      />

      <div
        role="tabpanel"
        id={tabPanelId("venue", tab)}
        aria-labelledby={tabId("venue", tab)}
        tabIndex={0}
        className="tab-panel"
      >
        {tab === "spaces" ? (
          <SpacesPanel
            organization={organization}
            venue={venue}
            spaces={spaces}
            sports={sportsQuery.data ?? []}
            bands={bandsQuery.data ?? []}
            selectedSpaceId={selectedSpaceId}
            onSelectSpace={selectSpace}
          />
        ) : (
          <PhotosPanel
            organization={organization}
            venue={venue}
            spaces={spaces}
            photos={photos}
            canReview={canReview}
            loading={photosQuery.isPending}
            error={photosQuery.error}
            onRetry={() => void photosQuery.refetch()}
          />
        )}
      </div>
    </>
  );
}
