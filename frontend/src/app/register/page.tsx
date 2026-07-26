import Link from "next/link";

import { AuthCard } from "@/components/auth/AuthCard";
import { RegisterForm } from "@/components/auth/RegisterForm";

export default function RegisterPage() {
  return (
    <AuthCard
      footer={
        <>
          Already have an account? <Link href="/login">Log in</Link>
        </>
      }
    >
      <RegisterForm />
    </AuthCard>
  );
}
