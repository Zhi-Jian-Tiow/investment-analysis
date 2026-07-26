import Link from "next/link";

import { AuthCard } from "@/components/auth/AuthCard";
import { ForgotPasswordForm } from "@/components/auth/ForgotPasswordForm";

export default function ForgotPasswordPage() {
  return (
    <AuthCard
      width={400}
      footer={
        <>
          Remembered your password? <Link href="/login">Log in</Link>
        </>
      }
    >
      <ForgotPasswordForm />
    </AuthCard>
  );
}
