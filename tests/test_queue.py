import tempfile
import threading
import time
import unittest
from pathlib import Path

from hermes_cfe.queue import DurableJobQueue, LeaseConflict


class DurableQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/"jobs.sqlite3"
        self.queue=DurableJobQueue(self.db,lease_seconds=1,max_attempts=3,base_retry_seconds=0)

    def tearDown(self):
        self.queue.close()
        self.tmp.cleanup()

    def test_enqueue_is_idempotent_on_exact_object_identity(self):
        first=self.queue.enqueue("cfe-bills","cfe/000000000001/bill.pdf","version-a")
        second=self.queue.enqueue("cfe-bills","cfe/000000000001/bill.pdf","version-a")
        changed=self.queue.enqueue("cfe-bills","cfe/000000000001/bill.pdf","version-b")
        self.assertEqual(first.job_id,second.job_id)
        self.assertFalse(second.created)
        self.assertNotEqual(first.job_id,changed.job_id)
        self.assertTrue(changed.created)

    def test_claim_uses_unique_lease_and_only_one_worker_gets_job(self):
        self.queue.enqueue("cfe-bills","cfe/000000000001/bill.pdf","v1")
        barrier=threading.Barrier(3); claims=[]; errors=[]
        def worker(name):
            try:
                barrier.wait(); claims.append(self.queue.claim(name))
            except Exception as exc:
                errors.append(exc)
        threads=[threading.Thread(target=worker,args=(f"w{i}",)) for i in range(2)]
        self.queue.close()
        self.queue=DurableJobQueue(self.db,lease_seconds=1,max_attempts=3,base_retry_seconds=0)
        for t in threads:t.start()
        barrier.wait()
        for t in threads:t.join()
        got=[c for c in claims if c is not None]
        self.assertEqual(errors,[])
        self.assertEqual(len(got),1)
        self.assertTrue(got[0].lease_token)

    def test_expired_lease_is_reclaimed_and_stale_owner_cannot_finish(self):
        self.queue.enqueue("cfe-bills","cfe/000000000001/bill.pdf","v1")
        old=self.queue.claim("worker-1")
        time.sleep(1.1)
        new=self.queue.claim("worker-2")
        self.assertEqual(new.job_id,old.job_id)
        self.assertNotEqual(new.lease_token,old.lease_token)
        with self.assertRaises(LeaseConflict): self.queue.finish(old,"harvested")
        self.queue.finish(new,"harvested",result={"cfdi_uuid":"AB12CD34-EF56-7890-ABCD-EF1234567890"})
        self.assertEqual(self.queue.get(new.job_id).state,"harvested")

    def test_retryable_failure_requeues_with_attempt_budget_and_terminal_after_limit(self):
        self.queue.enqueue("cfe-bills","cfe/000000000001/bill.pdf","v1")
        for attempt in (1,2):
            lease=self.queue.claim(f"w{attempt}")
            self.queue.fail(lease,"temporary",retryable=True)
        lease=self.queue.claim("w3")
        self.assertEqual(lease.attempts,3)
        self.queue.fail(lease,"still-temporary",retryable=True)
        row=self.queue.get(lease.job_id)
        self.assertEqual(row.state,"failed")
        self.assertIsNone(self.queue.claim("w4"))

    def test_business_exception_is_terminal_and_never_retried(self):
        self.queue.enqueue("cfe-bills","cfe/000000000001/bill.pdf","v1")
        lease=self.queue.claim("w1")
        self.queue.fail(lease,"CONTIGO_ACCOUNT_VERIFIED_CREDENTIAL_MISSING",retryable=False)
        self.assertEqual(self.queue.get(lease.job_id).state,"business_exception")
        self.assertIsNone(self.queue.claim("w2"))

    def test_state_transition_requires_current_lease_token(self):
        self.queue.enqueue("cfe-bills","cfe/000000000001/bill.pdf","v1")
        lease=self.queue.claim("w1")
        with self.assertRaises(LeaseConflict):
            self.queue.finish(type(lease)(**{**lease.__dict__,"lease_token":"not-the-token"}),"harvested")

    def test_database_reopen_preserves_queued_job(self):
        item=self.queue.enqueue("cfe-bills","cfe/000000000001/bill.pdf","v1")
        self.queue.close()
        self.queue=DurableJobQueue(self.db,lease_seconds=1,max_attempts=3,base_retry_seconds=0)
        lease=self.queue.claim("restarted-worker")
        self.assertEqual(lease.job_id,item.job_id)


if __name__=="__main__": unittest.main()
