interface RoutePlaceholderProps {
  title: string;
  description: string;
}

function RoutePlaceholder({ title, description }: RoutePlaceholderProps) {
  return (
    <section className="mx-auto flex w-full max-w-[1200px] flex-1 flex-col gap-2 px-4 py-10 sm:px-8 lg:px-12">
      <h1>{title}</h1>
      <p className="text-muted-foreground">{description}</p>
    </section>
  );
}

export default RoutePlaceholder;
