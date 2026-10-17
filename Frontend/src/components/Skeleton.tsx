export function PaperSkeleton() {
  return (
    <div className="paper-texture pb-20">
      <div className="mx-auto max-w-broadsheet px-4 py-10 sm:px-6">
        {/* Masthead skeleton */}
        <div className="text-center">
          <div className="mx-auto h-3 w-32 animate-pulse rounded bg-ink/10 dark:bg-cream-ink/10" />
          <div className="mx-auto mt-2 h-10 w-32 animate-pulse rounded bg-ink/15 dark:bg-cream-ink/15" />
          <div className="mx-auto mt-2 h-3 w-48 animate-pulse rounded bg-ink/10 dark:bg-cream-ink/10" />
        </div>
        <div className="mx-auto mt-4 max-w-md border-t-[3px] double border-ink/15 dark:border-cream-ink/15" />

        {/* Toolbar skeleton */}
        <div className="mt-6 flex items-center justify-between">
          <div className="h-4 w-40 animate-pulse rounded bg-ink/10 dark:bg-cream-ink/10" />
          <div className="flex gap-2">
            <div className="h-8 w-24 animate-pulse rounded-full bg-ink/10 dark:bg-cream-ink/10" />
            <div className="h-8 w-20 animate-pulse rounded-full bg-ink/10 dark:bg-cream-ink/10" />
          </div>
        </div>

        {/* Ticker skeleton */}
        <div className="mt-4 border-y border-ink/10 py-2 dark:border-cream-ink/10">
          <div className="h-3 w-full animate-pulse rounded bg-ink/8 dark:bg-cream-ink/8" />
        </div>

        {/* Lead skeleton */}
        <div className="mt-8">
          <div className="h-3 w-24 animate-pulse rounded bg-ink/10 dark:bg-cream-ink/10" />
          <div className="mt-3 h-10 w-3/4 animate-pulse rounded bg-ink/15 dark:bg-cream-ink/15" />
          <div className="mt-2 h-10 w-2/3 animate-pulse rounded bg-ink/12 dark:bg-cream-ink/12" />
          <div className="mt-4 h-5 w-full animate-pulse rounded bg-ink/8 dark:bg-cream-ink/8" />
          <div className="mt-2 h-5 w-5/6 animate-pulse rounded bg-ink/8 dark:bg-cream-ink/8" />
          <div className="mt-2 h-5 w-4/5 animate-pulse rounded bg-ink/8 dark:bg-cream-ink/8" />
        </div>

        <div className="my-10 rule-double border-ink/15 dark:border-cream-ink/15" />

        {/* Standard stories grid skeleton */}
        <div className="grid gap-10 md:grid-cols-2 md:gap-x-12">
          {[0, 1, 2, 3].map((i) => (
            <div key={i}>
              <div className="h-3 w-20 animate-pulse rounded bg-ink/10 dark:bg-cream-ink/10" />
              <div className="mt-2 h-8 w-full animate-pulse rounded bg-ink/12 dark:bg-cream-ink/12" />
              <div className="mt-2 h-4 w-full animate-pulse rounded bg-ink/8 dark:bg-cream-ink/8" />
              <div className="mt-1 h-4 w-3/4 animate-pulse rounded bg-ink/8 dark:bg-cream-ink/8" />
              <div className="mt-3 h-3 w-32 animate-pulse rounded bg-ink/8 dark:bg-cream-ink/8" />
            </div>
          ))}
        </div>

        {/* Briefs skeleton */}
        <div className="my-10 rule-thin border-ink/15 dark:border-cream-ink/15" />
        <div className="grid gap-10 md:grid-cols-3">
          <div>
            <div className="h-6 w-24 animate-pulse rounded bg-ink/12 dark:bg-cream-ink/12" />
            <div className="mt-4 space-y-3">
              {[0, 1, 2].map((i) => (
                <div key={i}>
                  <div className="h-4 w-full animate-pulse rounded bg-ink/8 dark:bg-cream-ink/8" />
                  <div className="mt-1 h-3 w-5/6 animate-pulse rounded bg-ink/8 dark:bg-cream-ink/8" />
                </div>
              ))}
            </div>
          </div>
          <div className="md:col-span-2">
            <div className="h-3 w-20 animate-pulse rounded bg-ink/10 dark:bg-cream-ink/10" />
            <div className="mt-2 h-8 w-3/4 animate-pulse rounded bg-ink/12 dark:bg-cream-ink/12" />
            <div className="mt-3 h-4 w-full animate-pulse rounded bg-ink/8 dark:bg-cream-ink/8" />
            <div className="mt-2 h-4 w-5/6 animate-pulse rounded bg-ink/8 dark:bg-cream-ink/8" />
            <div className="mt-2 h-4 w-4/5 animate-pulse rounded bg-ink/8 dark:bg-cream-ink/8" />
          </div>
        </div>
      </div>
    </div>
  );
}

export function ArchiveSkeleton() {
  return (
    <div className="paper-texture min-h-[calc(100vh-4rem)]">
      <div className="mx-auto max-w-broadsheet px-4 py-12 sm:px-6">
        <div className="text-center">
          <div className="mx-auto h-3 w-24 animate-pulse rounded bg-ink/10 dark:bg-cream-ink/10" />
          <div className="mx-auto mt-2 h-12 w-48 animate-pulse rounded bg-ink/15 dark:bg-cream-ink/15" />
        </div>
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
            <div
              key={i}
              className="rounded-sm border border-ink/15 bg-paper/50 p-4 dark:border-cream-ink/15 dark:bg-navy-2/50"
            >
              <div className="flex justify-between">
                <div className="h-2.5 w-20 animate-pulse rounded bg-ink/10 dark:bg-cream-ink/10" />
                <div className="h-2.5 w-10 animate-pulse rounded bg-ink/10 dark:bg-cream-ink/10" />
              </div>
              <div className="mx-auto mt-1 h-5 w-16 animate-pulse rounded bg-ink/12 dark:bg-cream-ink/12" />
              <div className="mt-3 h-2 w-full border-t border-ink/10 dark:border-cream-ink/10" />
              <div className="mt-3 h-2 w-16 animate-pulse rounded bg-ink/10 dark:bg-cream-ink/10" />
              <div className="mt-2 h-5 w-full animate-pulse rounded bg-ink/12 dark:bg-cream-ink/12" />
              <div className="mt-1 h-5 w-4/5 animate-pulse rounded bg-ink/10 dark:bg-cream-ink/10" />
              <div className="mt-2 h-3 w-full animate-pulse rounded bg-ink/8 dark:bg-cream-ink/8" />
              <div className="mt-1 h-3 w-3/4 animate-pulse rounded bg-ink/8 dark:bg-cream-ink/8" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function ProfileSkeleton() {
  return (
    <div className="paper-texture min-h-[calc(100vh-4rem)]">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        {/* Header */}
        <div className="text-center">
          <div className="mx-auto h-3 w-24 animate-pulse rounded bg-ink/10 dark:bg-cream-ink/10" />
          <div className="mx-auto mt-2 h-10 w-40 animate-pulse rounded bg-ink/15 dark:bg-cream-ink/15" />
        </div>

        {/* Stats */}
        <div className="mt-8 grid grid-cols-3 gap-px border border-ink/15 bg-ink/15 dark:border-cream-ink/15 dark:bg-cream-ink/15">
          {[0, 1, 2].map((i) => (
            <div key={i} className="bg-paper p-4 dark:bg-navy">
              <div className="mx-auto h-2.5 w-16 animate-pulse rounded bg-ink/10 dark:bg-cream-ink/10" />
              <div className="mx-auto mt-1.5 h-6 w-12 animate-pulse rounded bg-ink/15 dark:bg-cream-ink/15" />
            </div>
          ))}
        </div>

        {/* Weight bars */}
        <div className="mt-12 space-y-5">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i}>
              <div className="flex justify-between">
                <div className="h-4 w-24 animate-pulse rounded bg-ink/12 dark:bg-cream-ink/12" />
                <div className="h-4 w-12 animate-pulse rounded bg-ink/10 dark:bg-cream-ink/10" />
              </div>
              <div className="mt-2 h-2 w-full animate-pulse rounded-full bg-ink/10 dark:bg-cream-ink/10" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
